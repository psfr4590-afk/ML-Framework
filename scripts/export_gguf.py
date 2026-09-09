"""Export a Model Lab checkpoint through the official llama.cpp converter."""
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

from pipeline.trainer.model import LlamaModel, ModelConfig

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
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict) or "model" not in payload or "model_cfg" not in payload:
        raise RuntimeError(f"Checkpoint schema invalid: {path}")
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


def _hf_config(cfg: ModelConfig, model_name: str) -> dict[str, Any]:
    return {
        "architectures": ["LlamaForCausalLM"], "model_type": "llama",
        "torch_dtype": "float32", "vocab_size": cfg.vocab_size,
        "hidden_size": cfg.d_model, "intermediate_size": cfg.d_ffn,
        "num_hidden_layers": cfg.n_layers, "num_attention_heads": cfg.n_heads,
        "num_key_value_heads": cfg.n_kv_heads, "max_position_embeddings": cfg.seq_len,
        "rms_norm_eps": cfg.norm_eps, "rope_theta": cfg.rope_theta,
        "attention_bias": cfg.bias, "mlp_bias": cfg.bias,
        "tie_word_embeddings": True, "bos_token_id": 2, "eos_token_id": 3,
        "pad_token_id": 0, "_name_or_path": model_name,
    }


def _map_state(state: dict[str, torch.Tensor], cfg: ModelConfig) -> dict[str, torch.Tensor]:
    """Map Model Lab tensor names to standard Hugging Face Llama names."""
    del cfg
    table = {
        "norm1.weight": "input_layernorm.weight",
        "norm2.weight": "post_attention_layernorm.weight",
        "attn.q_proj.weight": "self_attn.q_proj.weight",
        "attn.k_proj.weight": "self_attn.k_proj.weight",
        "attn.v_proj.weight": "self_attn.v_proj.weight",
        "attn.o_proj.weight": "self_attn.o_proj.weight",
        "ffn.gate.weight": "mlp.gate_proj.weight",
        "ffn.up.weight": "mlp.up_proj.weight",
        "ffn.down.weight": "mlp.down_proj.weight",
    }
    out: dict[str, torch.Tensor] = {}
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
            idx = parts[1]
            tail = ".".join(parts[2:])
            if tail not in table:
                raise RuntimeError(f"Unsupported model tensor: {key}")
            mapped = f"model.layers.{idx}.{table[tail]}"
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
    if not tokenizer_json.is_file():
        raise FileNotFoundError(f"Tokenizer file does not exist: {tokenizer_json}")
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"):
        src = tokenizer_dir / name
        if src.exists():
            shutil.copy2(src, hf_dir / name)


def _find_converter(llamacpp_dir: Path) -> Path:
    for candidate in (llamacpp_dir / "convert_hf_to_gguf.py", llamacpp_dir / "convert_hf_to_gguf_update.py"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"llama.cpp converter not found under {llamacpp_dir}")


def _run(cmd: list[str], cwd: Path) -> None:
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
    if not out.is_file() or out.stat().st_size <= 0:
        raise RuntimeError("llama.cpp conversion produced no GGUF")
    return out


def _find_quantizer(llamacpp_dir: Path) -> Path:
    for name in ("llama-quantize", "llama-quantize.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for base in (llamacpp_dir / "build", llamacpp_dir / "bin", llamacpp_dir):
        if base.is_dir():
            for name in ("llama-quantize", "llama-quantize.exe"):
                matches = list(base.rglob(name))
                if matches:
                    return matches[0]
    raise FileNotFoundError("llama-quantize executable not found")


def _quantize(f16: Path, quantizer: Path, quant: str, gguf_dir: Path) -> Path:
    out = gguf_dir / f"model-{quant.lower()}.gguf"
    _run([str(quantizer), str(f16), str(out), quant], quantizer.parent)
    if not out.is_file() or out.stat().st_size <= 0:
        raise RuntimeError("Quantization produced no GGUF")
    return out


def export_checkpoint(output_dir: str | Path, llamacpp_dir: str | Path, quant: str = "Q4_K_M", model_name: str = "pretrain-model", checkpoint: str | Path | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    llamacpp_dir = Path(llamacpp_dir).resolve()
    quant = quant.upper()
    if quant not in QUANTS:
        raise ValueError(f"Unsupported quantization '{quant}'")
    ckpt = Path(checkpoint).resolve() if checkpoint else _find_best_checkpoint(output_dir / "checkpoints")
    state, cfg, payload = _load_checkpoint(ckpt)
    tokenizer_dir = output_dir / "tokenizer"
    tok = tokenizer_dir / "tokenizer.json"
    if not tok.is_file():
        raise FileNotFoundError(f"Tokenizer is missing: {tok}")
    data = json.loads(tok.read_text(encoding="utf-8"))
    vocab = data.get("model", {}).get("vocab", {})
    if not isinstance(vocab, dict) or len(vocab) != cfg.vocab_size:
        raise RuntimeError("Tokenizer vocab size does not match model vocab size")
    hf_dir = output_dir / "export" / "hf"
    gguf_dir = output_dir / "gguf"
    _write_hf_checkpoint(state, cfg, hf_dir, model_name)
    _tokenizer_files(tokenizer_dir, hf_dir)
    converter = _find_converter(llamacpp_dir)
    f16 = _convert_to_f16(converter, hf_dir, gguf_dir)
    final = f16 if quant == "F16" else _quantize(f16, _find_quantizer(llamacpp_dir), quant, gguf_dir)
    modelfile = gguf_dir / "Modelfile"
    modelfile.write_text(f"FROM {final.name}\n\nPARAMETER temperature 0.7\nPARAMETER top_p 0.9\nPARAMETER repeat_penalty 1.1\n", encoding="utf-8")
    from pipeline.integrity import sha256_file
    manifest = {
        "schema": 2, "checkpoint": str(ckpt), "checkpoint_step": int(payload.get("step", 0)),
        "model_name": model_name, "model_config": cfg.to_dict(), "quantization": quant,
        "llamacpp_dir": str(llamacpp_dir), "converter": str(converter),
        "hf_dir": str(hf_dir), "f16_gguf": str(f16), "final_gguf": str(final),
        "final_gguf_sha256": sha256_file(final), "final_gguf_size": final.stat().st_size,
        "f16_gguf_sha256": sha256_file(f16), "modelfile": str(modelfile),
    }
    _atomic_json(gguf_dir / "export_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a Model Lab checkpoint to GGUF/Ollama")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--llamacpp-dir", required=True)
    parser.add_argument("--quant", default="Q4_K_M", choices=sorted(QUANTS))
    parser.add_argument("--model-name", default="pretrain-model")
    parser.add_argument("--checkpoint")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    try:
        export_checkpoint(args.output_dir, args.llamacpp_dir, args.quant, args.model_name, args.checkpoint)
    except Exception as exc:
        log.error("Export failed: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
