from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from pipeline.orchestrator import Pipeline
from pipeline.trainer.model import LlamaModel, ModelConfig
from pipeline.integrity import write_manifest
from scripts.export_gguf import _enforce_training_provenance, _load_checkpoint, _map_state
from command_center.store import DatasetStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_default_config_is_project_rooted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline()
    assert pipeline._project_root == REPO_ROOT
    assert pipeline._cfg_path == REPO_ROOT / "config" / "pipeline_config.yaml"


def test_pipeline_no_resume_disables_artifact_and_checkpoint_resume(tmp_path):
    source = REPO_ROOT / "config" / "pipeline_config.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    config["pipeline"]["resume"] = True
    config["train"]["resume"] = True
    config["pipeline"]["output_dir"] = str(tmp_path / "output")
    config["pipeline"]["scratch_dir"] = str(tmp_path / "scratch")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    pipeline = Pipeline(str(config_path), resume=False)
    assert pipeline._resume is False
    assert pipeline.cfg["train"]["resume"] is False


def test_pipeline_all_honors_configured_stage_enablement(monkeypatch):
    pipeline = Pipeline()
    calls: list[str] = []

    monkeypatch.setattr(pipeline, "stage_crawl", lambda group=None: calls.append("crawl") or Path("crawl"))
    monkeypatch.setattr(pipeline, "stage_clean", lambda path: calls.append("clean") or Path("clean"))
    monkeypatch.setattr(pipeline, "stage_embed_dedup", lambda path: calls.append("dedup") or Path("dedup"))
    monkeypatch.setattr(pipeline, "stage_weight", lambda path: calls.append("weight") or Path("weight"))
    monkeypatch.setattr(pipeline, "stage_tokenize", lambda path: calls.append("tokenize") or object())
    monkeypatch.setattr(pipeline, "stage_shard", lambda path, tokenizer: calls.append("shard") or Path("shard"))
    monkeypatch.setattr(pipeline, "stage_train", lambda: calls.append("train") or Path("checkpoint"))
    monkeypatch.setattr(pipeline, "stage_export", lambda: calls.append("export"))

    pipeline.run("all")
    assert calls == ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train"]


def test_model_param_count_respects_weight_tying():
    cfg = ModelConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=16)
    model = LlamaModel(cfg)
    assert model.param_count() == sum(p.numel() for p in model.parameters())


def test_export_mapping_produces_standard_llama_tensor_names():
    cfg = ModelConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=16)
    model = LlamaModel(cfg)
    mapped = _map_state(model.state_dict(), cfg)
    required = {
        "model.embed_tokens.weight",
        "model.layers.0.input_layernorm.weight",
        "model.layers.0.self_attn.q_proj.weight",
        "model.layers.0.self_attn.k_proj.weight",
        "model.layers.0.self_attn.v_proj.weight",
        "model.layers.0.self_attn.o_proj.weight",
        "model.layers.0.post_attention_layernorm.weight",
        "model.layers.0.mlp.gate_proj.weight",
        "model.layers.0.mlp.up_proj.weight",
        "model.layers.0.mlp.down_proj.weight",
        "model.norm.weight",
        "lm_head.weight",
    }
    assert required <= set(mapped)


def test_export_load_checkpoint_uses_canonical_integrity_gate(tmp_path):
    from pipeline.trainer.train import save_checkpoint

    cfg = ModelConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=16)
    model = LlamaModel(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    path = save_checkpoint(model, optimizer, scaler, 1, 2.5, {"model_preset": "test"}, tmp_path)

    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        _load_checkpoint(path)


def test_dataset_store_reports_pipeline_artifacts_under_output(tmp_path, monkeypatch):
    import command_center.store as module
    monkeypatch.setattr(module, "DATASETS", tmp_path / "datasets")
    store = DatasetStore()
    meta = store.create("Test", group_config={"id": "custom", "name": "Test", "sources": {}})
    root = store.path(meta["id"])
    out = root / "output"
    (out / "tokenizer").mkdir(parents=True)
    tokenizer = out / "tokenizer" / "tokenizer.json"
    tokenizer.write_text("{}", encoding="utf-8")
    write_manifest(tokenizer, kind="tokenizer")
    state = store.refresh_pipeline_state(meta["id"])
    assert state["stages"]["tokenize"] == "complete"


def test_checkpoint_roundtrip_integrity(tmp_path):
    from pipeline.trainer.train import save_checkpoint, load_checkpoint
    cfg = ModelConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=16)
    model = LlamaModel(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    path = save_checkpoint(model, optimizer, scaler, 1, 2.5, {"model_preset": "test"}, tmp_path)
    assert path.exists()
    assert path.with_name(path.name + ".manifest.json").exists()
    reloaded = LlamaModel(cfg)
    opt2 = torch.optim.AdamW(reloaded.parameters(), lr=1e-3)
    scaler2 = torch.amp.GradScaler("cuda", enabled=False)
    assert load_checkpoint(path, reloaded, opt2, scaler2, torch.device("cpu")) == 1


def test_checkpoint_resume_restores_exact_loader_cursor(tmp_path):
    from pipeline.shardwriter.shard_writer import ShardDataLoader
    from pipeline.trainer.train import load_checkpoint, save_checkpoint

    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    files = []
    for split, start in (("train", 0), ("val", 100)):
        path = shard_dir / f"shard_00000_{split}.bin"
        path.write_bytes(np.arange(start, start + 64, dtype=np.uint16).tobytes())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"name": path.name, "size": path.stat().st_size, "sha256": digest})
    (shard_dir / "shards.manifest.json").write_text(
        json.dumps({"version": 1, "dtype": "uint16", "sequence_length": 8, "vocab_size": 200, "files": files}),
        encoding="utf-8",
    )

    train = ShardDataLoader(shard_dir, "train", 8, seed=17)
    val = ShardDataLoader(shard_dir, "val", 8, seed=17)
    model_cfg = ModelConfig(vocab_size=32, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=8)
    model = LlamaModel(model_cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cuda", enabled=False)
    provenance = {"schema": 1, "pipeline_config_sha256": "a" * 64, "train_config_sha256": "b" * 64, "model_config_sha256": "c" * 64, "shard_manifest_sha256": "d" * 64, "seed": 17}

    train.next_batch(1)
    val.next_batch(1)
    path = save_checkpoint(model, optimizer, scaler, 3, 1.5, {"seed": 17}, tmp_path / "checkpoints", provenance=provenance, train_loader=train, val_loader=val)
    expected_x, expected_y = train.next_batch(1)

    resumed_model = LlamaModel(model_cfg)
    resumed_optimizer = torch.optim.AdamW(resumed_model.parameters(), lr=1e-3)
    resumed_scaler = torch.amp.GradScaler("cuda", enabled=False)
    resumed_train = ShardDataLoader(shard_dir, "train", 8, seed=17)
    resumed_val = ShardDataLoader(shard_dir, "val", 8, seed=17)
    assert load_checkpoint(path, resumed_model, resumed_optimizer, resumed_scaler, torch.device("cpu"), expected_provenance=provenance, train_loader=resumed_train, val_loader=resumed_val) == 3
    actual_x, actual_y = resumed_train.next_batch(1)
    assert torch.equal(actual_x, expected_x)
    assert torch.equal(actual_y, expected_y)


def test_export_provenance_rejects_missing_or_mismatched_lineage(tmp_path):
    with pytest.raises(RuntimeError, match="incomplete"):
        _enforce_training_provenance(tmp_path / "output", {"provenance": {}})


def test_semantic_dedup_has_dependency_free_fallback(monkeypatch):
    import pipeline.embedder.semantic_dedup as module
    from pipeline.types import Document

    monkeypatch.setattr(module, "ST_AVAILABLE", False)
    deduper = module.SemanticDeduplicator({"similarity_threshold": 0.8})
    docs = [
        Document(doc_id="a", text="alpha beta gamma delta", final_weight=1.0),
        Document(doc_id="b", text="alpha beta gamma delta", final_weight=0.5),
        Document(doc_id="c", text="completely unrelated content", final_weight=1.0),
    ]
    kept = deduper.run(docs)
    assert [d.doc_id for d in kept] == ["a", "c"]
