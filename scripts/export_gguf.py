#!/usr/bin/env python3
"""Production export path: native checkpoint -> Hugging Face -> GGUF -> Ollama."""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch

from pipeline.integrity import sha256_file, validate_checkpoint
from pipeline.trainer.model import LlamaModel, ModelConfig
from scripts.export_cards import write_export_cards

log = logging.getLogger("export")
QUANTS = {"F16", "Q4_K_M", "Q5_K_M", "Q8_0"}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _find_best_checkpoint(checkpoint_dir: Path) -> Path:
    candidates = list(checkpoint_dir.glob("ckpt_best_*.pt")) or list(checkpoint_dir.glob("ckpt_final_*.pt")) or list(checkpoint_dir.glob("ckpt_*.pt"))
    if not candidates:
        raise FileNotFoundError(f"No training checkpoint found in {checkpoint_dir}")
    def step(path: Path) -> int:
        try:
            return int(path.stem.rsplit("_", 1)[-1])
        except ValueError:
            return -1
    return max(candidates, key=lambda p: (step(p), p.stat().st_mtime_ns))


def _load_checkpoint(path: Path) -> tuple[dict[str, torch.Tensor], ModelConfig, dict[str, Any]]:
    payload = validate_checkpoint(path)
    cfg = ModelConfig.from_dict(payload["model_cfg"])
    state = payload["model"]
    if not isinstance(state, dict):
        raise RuntimeError(f"Checkpoint model state is not a mapping: {path}")
    model = LlamaModel(cfg)
    try:
        missing, unexpected = model.load_state_dict(state, strict=False)
    except RuntimeError as exc:
        raise RuntimeError(f"Checkpoint tensor shapes do not match its model config: {exc}") from exc
    missing = [x for x in missing if x not in {"rope_cos", "rope_sin"}]
    if missing or unexpected:
        raise RuntimeError(f"Checkpoint state is incompatible. Missing={missing}, unexpected={unexpected}")
    return state, cfg, payload


def _enforce_training_provenance(output_dir: Path, payload: dict[str, Any]) -> None:
    """Refuse export unless the checkpoint and retained upstream artifacts agree."""
    provenance = payload.get("provenance") or {}
    required = ("schema", "pipeline_config_sha256", "train_config_sha256", "model_config_sha256", "shard_manifest_sha256", "seed")
    missing = [key for key in required if key not in provenance or provenance[key] in (None, "")]
    if missing:
        raise RuntimeError(f"Checkpoint provenance is incomplete; refusing export: {missing}")

    shard_manifest = output_dir / "shards" / "shards.manifest.json"
    tokenizer_manifest = output_dir / "tokenizer" / "tokenizer.json.manifest.json"
    weighted_manifest = output_dir.parent / "scratch" / "04_weighted.jsonl.manifest.json"
    for path in (shard_manifest, tokenizer_manifest, weighted_manifest):
        if not path.is_file():
            raise RuntimeError(f"Required provenance artifact is missing; refusing export: {path}")

    try:
        shard_data = json.loads(shard_manifest.read_text(encoding="utf-8"))
        tokenizer_data = json.loads(tokenizer_manifest.read_text(encoding="utf-8"))
        weighted_data = json.loads(weighted_manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Required provenance manifest is invalid; refusing export") from exc

    shard_sha = sha256_file(shard_manifest)
    if shard_sha != provenance["shard_manifest_sha256"]:
        raise RuntimeError("Checkpoint shard-manifest identity does not match current shards; refusing export")
    for label, data in (("tokenizer", tokenizer_data), ("weighted", weighted_data)):
        stage_prov = data.get("provenance") or {}
        if stage_prov.get("pipeline_config_sha256") != provenance["pipeline_config_sha256"]:
            raise RuntimeError(f"{label} provenance does not belong to the checkpoint pipeline configuration; refusing export")
    if shard_data.get("provenance", {}).get("pipeline_config_sha256") != provenance["pipeline_config_sha256"]:
        raise RuntimeError("Shard provenance does not belong to the checkpoint pipeline configuration; refusing export")
    if int(tokenizer_data.get("vocab_size", -1)) != int(payload["model_cfg"].get("vocab_size", -2)):
        raise RuntimeError("Tokenizer/model vocabulary provenance mismatch; refusing export")


def _hf_config(cfg: ModelConfig, model_name: str) -> dict[str, Any]:
    return {"architectures":["LlamaForCausalLM"],"model_type":"llama","torch_dtype":"float32","vocab_size":cfg.vocab_size,"hidden_size":cfg.d_model,"intermediate_size":cfg.d_ffn,"num_hidden_layers":cfg.n_layers,"num_attention_heads":cfg.n_heads,"num_key_value_heads":cfg.n_kv_heads,"max_position_embeddings":cfg.seq_len,"rms_norm_eps":cfg.norm_eps,"rope_theta":cfg.rope_theta,"attention_bias":cfg.bias,"mlp_bias":cfg.bias,"tie_word_embeddings":True,"bos_token_id":2,"eos_token_id":3,"pad_token_id":0,"transformers_version":"4.0+","_name_or_path":model_name}


def _map_state(state: dict[str, torch.Tensor], cfg: ModelConfig) -> dict[str, torch.Tensor]:
    out: dict[str, torch.Tensor] = {}
    table = {"norm1.weight":"input_layernorm.weight","norm2.weight":"post_attention_layernorm.weight","attn.q_proj.weight":"self_attn.q_proj.weight","attn.k_proj.weight":"self_attn.k_proj.weight","attn.v_proj.weight":"self_attn.v_proj.weight","attn.o_proj.weight":"self_attn.o_proj.weight","ffn.gate.weight":"mlp.gate_proj.weight","ffn.up.weight":"mlp.up_proj.weight","ffn.down.weight":"mlp.down_proj.weight"}
    for key, value in state.items():
        if key in {"rope_cos", "rope_sin"}:
            continue
        if key == "embed.weight":
            mapped = "model.embed_tokens.weight"
        elif key == "norm.weight":
            mapped = "model.norm.weight"
        elif key == "lm_head.weight":
            mapped = "lm_head.weight"
        elif key.startswith("blocks."):
            parts = key.split(".")
            tail = ".".join(parts[2:])
            try:
                mapped = f"model.layers.{parts[1]}.{table[tail]}"
            except KeyError as exc:
                raise RuntimeError(f"Unsupported model tensor: {key}") from exc
        else:
            raise RuntimeError(f"Unsupported model tensor: {key}")
        out[mapped] = value.detach().cpu().contiguous()
    if "model.embed_tokens.weight" not in out or "lm_head.weight" not in out:
        raise RuntimeError("Export requires both embedding and lm_head tensors")
    if out["model.embed_tokens.weight"].shape != out["lm_head.weight"].shape:
        raise RuntimeError("Embedding and lm_head shapes differ; refusing export")
    return out


def _write_hf_checkpoint(state: dict[str, torch.Tensor], cfg: ModelConfig, out: Path, model_name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    torch.save(_map_state(state, cfg), out / "pytorch_model.bin")
    _atomic_json(out / "config.json", _hf_config(cfg, model_name))
    return out


def _tokenizer_files(tokenizer_dir: Path, hf_dir: Path) -> None:
    tokenizer_json = tokenizer_dir / "tokenizer.json"
    if not tokenizer_json.exists():
        raise FileNotFoundError(f"Tokenizer file does not exist: {tokenizer_json}")
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        src = tokenizer_dir / name
        if src.exists():
            shutil.copy2(src, hf_dir / name)


def _llama_version(llamacpp_dir: Path) -> str:
    manifest = llamacpp_dir / "VENDOR_MANIFEST.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return f"{data.get('tag','unknown')}@{data.get('commit','unknown')}"
        except (OSError, json.JSONDecodeError):
            pass
    try:
        proc = subprocess.run(["git","rev-parse","HEAD"], cwd=llamacpp_dir, text=True, capture_output=True, check=False)
        if proc.returncode == 0:
            return proc.stdout.strip()
    except OSError:
        pass
    return "unknown"


def _find_converter(llamacpp_dir: Path) -> Path:
    for candidate in (llamacpp_dir / "convert_hf_to_gguf.py", llamacpp_dir / "convert_hf_to_gguf_update.py"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"llama.cpp converter not found under {llamacpp_dir}. Provide a current checkout containing convert_hf_to_gguf.py.")


def _run(cmd: list[str], cwd: Path) -> None:
    log.info("Running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    if proc.stdout:
        log.info(proc.stdout.rstrip())
    if proc.returncode != 0:
        if proc.stderr:
            log.error(proc.stderr.rstrip())
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")


def _convert_to_f16(converter: Path, hf_dir: Path, gguf_dir: Path) -> Path:
    gguf_dir.mkdir(parents=True, exist_ok=True)
    out = gguf_dir / "model-f16.gguf"
    _run([sys.executable, str(converter), str(hf_dir), "--outfile", str(out), "--outtype", "f16"], converter.parent)
    if not out.exists() or out.stat().st_size <= 0:
        raise RuntimeError("llama.cpp conversion completed without producing a GGUF file")
    return out


def _find_quantizer(llamacpp_dir: Path) -> Path:
    names = ["llama-quantize", "llama-quantize.exe"]
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    for base in (llamacpp_dir / "build", llamacpp_dir / "bin", llamacpp_dir):
        if base.is_dir():
            for name in names:
                matches = list(base.rglob(name))
                if matches:
                    return matches[0]
    raise FileNotFoundError("llama-quantize executable not found; build the pinned llama.cpp checkout before requesting a quantized GGUF")


def _quantize(f16: Path, quantizer: Path, quant: str, gguf_dir: Path) -> Path:
    out = gguf_dir / f"model-{quant.lower()}.gguf"
    _run([str(quantizer), str(f16), str(out), quant], quantizer.parent)
    if not out.exists() or out.stat().st_size <= 0:
        raise RuntimeError("llama-quantize completed without producing the requested GGUF")
    return out


def export_checkpoint(output_dir: str | Path, llamacpp_dir: str | Path, quant: str = "Q4_K_M", model_name: str = "pretrain-model", checkpoint: str | Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    llamacpp_dir = Path(llamacpp_dir).resolve()
    quant = quant.upper()
    if quant not in QUANTS:
        raise ValueError(f"Unsupported quantization '{quant}'. Choose from {sorted(QUANTS)}")
    ckpt = Path(checkpoint).resolve() if checkpoint else _find_best_checkpoint(output_dir / "checkpoints")
    state, cfg, payload = _load_checkpoint(ckpt)
    _enforce_training_provenance(output_dir, payload)
    tokenizer_dir = output_dir / "tokenizer"
    tokenizer_json = tokenizer_dir / "tokenizer.json"
    if not tokenizer_json.is_file():
        raise FileNotFoundError(f"Tokenizer is missing: {tokenizer_json}")
    try:
        tok_data = json.loads(tokenizer_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tokenizer JSON is invalid: {tokenizer_json}") from exc
    vocab = tok_data.get("model", {}).get("vocab", {})
    if not isinstance(vocab, dict) or len(vocab) != cfg.vocab_size:
        raise RuntimeError(f"Tokenizer vocab ({len(vocab) if isinstance(vocab, dict) else 'invalid'}) does not match model vocab_size ({cfg.vocab_size})")
    hf_dir = output_dir / "export" / "hf"
    gguf_dir = output_dir / "gguf"
    _write_hf_checkpoint(state, cfg, hf_dir, model_name)
    _tokenizer_files(tokenizer_dir, hf_dir)
    converter = _find_converter(llamacpp_dir)
    f16 = _convert_to_f16(converter, hf_dir, gguf_dir)
    final = f16
    if quant != "F16":
        final = _quantize(f16, _find_quantizer(llamacpp_dir), quant, gguf_dir)
    modelfile = gguf_dir / "Modelfile"
    modelfile.write_text(f"FROM {final.name}\n\nPARAMETER temperature 0.7\nPARAMETER top_p 0.9\nPARAMETER repeat_penalty 1.1\n", encoding="utf-8")
    manifest = {
        "schema": 3,
        "checkpoint": str(ckpt),
        "checkpoint_step": int(payload.get("step", 0)),
        "model_name": model_name,
        "model_config": cfg.to_dict(),
        "quantization": quant,
        "llamacpp_dir": str(llamacpp_dir),
        "converter": str(converter),
        "converter_version": _llama_version(llamacpp_dir),
        "hf_dir": str(hf_dir),
        "f16_gguf": str(f16),
        "final_gguf": str(final),
        "final_gguf_sha256": sha256_file(final),
        "final_gguf_size": final.stat().st_size,
        "f16_gguf_sha256": sha256_file(f16),
        "modelfile": str(modelfile),
        "training_provenance": payload.get("provenance") or {},
    }
    card_paths = write_export_cards(output_dir, manifest, payload)
    manifest["dataset_card"] = card_paths["dataset_card"]
    manifest["model_card"] = card_paths["model_card"]
    manifest["dataset_card_sha256"] = sha256_file(Path(card_paths["dataset_card"]))
    manifest["model_card_sha256"] = sha256_file(Path(card_paths["model_card"]))
    _atomic_json(gguf_dir / "export_manifest.json", manifest)
    log.info("Export complete: %s", final)
    log.info("Dataset card: %s", card_paths["dataset_card"])
    log.info("Model card: %s", card_paths["model_card"])
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a Model Lab checkpoint to GGUF/Ollama")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--llamacpp-dir", required=True)
    parser.add_argument("--quant", default="Q4_K_M", choices=sorted(QUANTS))
    parser.add_argument("--model-name", default="pretrain-model")
    parser.add_argument("--checkpoint")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        export_checkpoint(args.output_dir, args.llamacpp_dir, args.quant, args.model_name, args.checkpoint)
    except Exception as exc:
        log.error("Export failed: %s", exc)
        return 2
    return 0
