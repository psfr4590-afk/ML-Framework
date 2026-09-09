from __future__ import annotations

from pathlib import Path

import torch

from pipeline.orchestrator import Pipeline
from pipeline.trainer.model import LlamaModel, ModelConfig
from pipeline.integrity import write_manifest
from scripts.export_gguf import _map_state
from command_center.store import DatasetStore


def test_pipeline_default_config_is_project_rooted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline()
    assert pipeline._project_root == Path(__file__).resolve().parents[1]
    assert pipeline._cfg_path == pipeline._project_root / "config" / "pipeline_config.yaml"


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
