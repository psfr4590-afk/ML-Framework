from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest
import numpy as np
import torch

from command_center import security, config as cc_config, web as cc_web
from fastapi import HTTPException
from pipeline import config_validation, doctor, integrity, model_sizer, orchestrator
from pipeline.embedder import semantic_dedup
from pipeline.types import Document
from pipeline.trainer.model import (
    Block,
    CausalSelfAttention,
    LlamaModel,
    ModelConfig,
    RMSNorm,
    SwiGLU,
    apply_rope,
    precompute_freqs,
)
from pipeline.trainer.train import (
    Trainer,
    _provenance,
    _restore_rng_state,
    _rng_state,
    _seed_everything,
    cosine_lr,
    latest_checkpoint,
    load_checkpoint,
    save_checkpoint,
)


def test_security_paths_and_limits(tmp_path, monkeypatch):
    root = tmp_path / "imports"
    root.mkdir()
    monkeypatch.setattr(security, "IMPORT_ROOT", root)
    data = root / "ok.txt"
    data.write_text("x", encoding="utf-8")
    assert security.resolved("~/../tmp").is_absolute()
    assert security.is_within(data, root)
    assert not security.is_within(tmp_path / "other", root)
    assert security.validate_import_source("ok.txt") == data
    with pytest.raises(FileNotFoundError):
        security.validate_import_source("missing.txt")

    datasets = tmp_path / "datasets"
    runtime = tmp_path / ".runtime"
    datasets.mkdir()
    runtime.mkdir()
    log = datasets / "app.log"
    log.write_text("x", encoding="utf-8")
    monkeypatch.setattr(security, "ROOT", tmp_path)
    assert security.validate_log_path(log) == log
    with pytest.raises(ValueError):
        security.validate_log_path(tmp_path / "outside.log")
    with pytest.raises(ValueError):
        security.validate_log_path(datasets / "notes.txt")
    link = datasets / "link.log"
    try:
        link.symlink_to(log)
    except (OSError, NotImplementedError):
        pass
    else:
        with pytest.raises(ValueError):
            security.validate_log_path(link)

    assert security.validate_tail_lines(-10) == 1
    assert security.validate_tail_lines(50) == 50
    assert security.validate_tail_lines(10_000) == security.MAX_LOG_LINES

    tree = tmp_path / "tree"
    (tree / "nested").mkdir(parents=True)
    (tree / "nested" / "ok.txt").write_text("x", encoding="utf-8")
    security.reject_symlink_tree(tree)
    bad = tree / "nested" / "bad"
    try:
        bad.symlink_to(log)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(ValueError):
        security.reject_symlink_tree(tree)


@pytest.mark.parametrize("name", ["85M", "117M", "360M"])
def test_model_config_presets_roundtrip(name):
    cfg = ModelConfig.from_preset(name)
    assert cfg.param_count() > 0
    restored = ModelConfig.from_dict({**cfg.to_dict(), "ignored": 1})
    assert restored == cfg


def test_model_components_and_model_forward_generate():
    cfg = ModelConfig(vocab_size=17, seq_len=8, n_layers=1, n_heads=2, n_kv_heads=1, d_model=8, d_ffn=16, dropout=0.0)
    model = LlamaModel(cfg)
    idx = torch.tensor([[1, 2, 3, 4]])
    targets = torch.tensor([[2, 3, 4, 5]])
    logits, loss = model(idx, targets)
    assert logits.shape == (1, 4, 17)
    assert loss is not None and torch.isfinite(loss)
    last, no_loss = model(idx)
    assert last.shape == (1, 1, 17)
    assert no_loss is None
    generated = model.generate(idx, 2, temperature=1.0, top_k=3)
    assert generated.shape == (1, 6)
    assert model.param_count() == sum(p.numel() for p in model.parameters())
    with pytest.raises(ValueError):
        model(torch.ones((1, 9), dtype=torch.long))
    with pytest.raises(ValueError):
        model.generate(idx, 1, temperature=0)
    assert isinstance(RMSNorm(8)(torch.randn(2, 8)), torch.Tensor)
    assert SwiGLU(8, 16)(torch.randn(2, 8)).shape == (2, 8)
    cos, sin = precompute_freqs(4, 5)
    assert cos.shape == sin.shape == (5, 2)
    with pytest.raises(ValueError):
        precompute_freqs(3, 5)
    x = torch.randn(1, 3, 2, 4)
    assert apply_rope(x, cos, sin).shape == x.shape
    block = Block(cfg)
    assert block(torch.randn(1, 4, 8), cos[:4], sin[:4]).shape == (1, 4, 8)


def test_attention_validation_and_gqa():
    with pytest.raises(ValueError):
        CausalSelfAttention(ModelConfig(d_model=7, n_heads=2, n_kv_heads=1))
    with pytest.raises(ValueError):
        CausalSelfAttention(ModelConfig(d_model=8, n_heads=3, n_kv_heads=2))
    cfg = ModelConfig(vocab_size=11, seq_len=4, n_layers=1, n_heads=4, n_kv_heads=2, d_model=8, d_ffn=12)
    attn = CausalSelfAttention(cfg)
    cos, sin = precompute_freqs(2, 4)
    out = attn(torch.randn(2, 4, 8), cos, sin)
    assert out.shape == (2, 4, 8)


def test_model_sizer_all_tiers_and_token_estimates(tmp_path, monkeypatch):
    tiers = [
        model_sizer.HardwareProfile("x", 2, 4, 0, 0, None, False),
        model_sizer.HardwareProfile("x", 2, 4, 1, 3, "a", True),
        model_sizer.HardwareProfile("x", 2, 4, 1, 5, "b", True),
        model_sizer.HardwareProfile("x", 2, 4, 1, 8, "c", True),
        model_sizer.HardwareProfile("x", 2, 4, 1, 16, "d", True),
        model_sizer.HardwareProfile("x", 2, 4, 1, 24, "e", True),
    ]
    assert [h.tier for h in tiers] == ["cpu", "gpu_<4gb", "gpu_4_6gb", "gpu_6_10gb", "gpu_10_20gb", "gpu_20gb_plus"]
    assert tiers[-1].to_dict()["tier"] == "gpu_20gb_plus"
    for h in tiers:
        profile = model_sizer.recommend_training_profile(h, total_tokens=100_000, configured_steps=100, max_seq_len=128)
        assert profile.recommended_steps >= 1
        assert profile.seq_len <= 128
    with pytest.raises(ValueError):
        model_sizer.recommend_training_profile(tiers[0], max_seq_len=0)
    timed = model_sizer.recommend_training_profile(tiers[-1], total_tokens=10_000_000, configured_steps=1000, target_training_hours=1, observed_tokens_per_sec=1000)
    assert timed.estimated_hours is not None

    shard = tmp_path / "shards"
    shard.mkdir()
    (shard / "shard_000_000.bin").write_bytes(b"\0" * 20)
    assert model_sizer.estimate_total_tokens(shard) == 10
    (shard / "shards.manifest.json").write_text(json.dumps({"dtype": "uint32", "files": [{"size": 40}]}), encoding="utf-8")
    assert model_sizer.estimate_total_tokens(shard) == 10
    (shard / "shards.manifest.json").write_text(json.dumps({"files": "bad"}), encoding="utf-8")
    with pytest.raises(ValueError):
        model_sizer.estimate_total_tokens(shard)
    (shard / "shards.manifest.json").unlink()
    for p in shard.glob("*.bin"):
        p.unlink()
    with pytest.raises(FileNotFoundError):
        model_sizer.estimate_total_tokens(shard)


def test_model_sizer_profile_hardware(monkeypatch):
    class FakeCuda:
        @staticmethod
        def is_available():
            return True
        @staticmethod
        def device_count():
            return 1
        @staticmethod
        def get_device_properties(_):
            return SimpleNamespace(total_memory=8 * 1024**3, name="Fake GPU")
    fake_torch = SimpleNamespace(cuda=FakeCuda)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(model_sizer, "_available_ram_gb", lambda: 12.5)
    p = model_sizer.profile_hardware()
    assert p.cuda_available and p.gpu_count == 1 and p.gpu_memory_gb == 8


def test_integrity_jsonl_and_artifacts(tmp_path):
    path = tmp_path / "data.jsonl"
    assert integrity.atomic_jsonl_write(path, [{"a": 1}, {"b": 2}]) == 2
    assert path.read_text(encoding="utf-8").count("\n") == 2
    raw = tmp_path / "raw.jsonl"
    assert integrity.atomic_jsonl_write(raw, lambda: ['{"x": 1}']) == 1
    with pytest.raises(ValueError):
        integrity.atomic_jsonl_write(tmp_path / "bad.jsonl", ["not-json"])
    with pytest.raises(RuntimeError):
        integrity.atomic_jsonl_write(tmp_path / "empty.jsonl", [])
    manifest = integrity.write_manifest(path, kind="jsonl", rows=2, provenance={"a": 1}, extra={"source": str(raw), "source_sha256": integrity.sha256_file(raw)})
    assert manifest.is_file()
    assert integrity.artifact_valid(path, {"a": 1})
    assert not integrity.artifact_valid(path, {"a": 2})
    path.write_text("tampered\n", encoding="utf-8")
    assert not integrity.artifact_valid(path)


def test_integrity_artifact_edge_cases(tmp_path):
    p = tmp_path / "x.bin"
    assert not integrity.artifact_valid(p)
    p.write_bytes(b"x")
    assert not integrity.artifact_valid(p)
    mp = integrity.manifest_path(p)
    mp.write_text("{", encoding="utf-8")
    assert not integrity.artifact_valid(p)
    mp.write_text(json.dumps({"schema": 999, "kind": "x"}), encoding="utf-8")
    assert not integrity.artifact_valid(p)
    p.write_bytes(b"abc")
    integrity.write_manifest(p, kind="bin")
    data = json.loads(mp.read_text(encoding="utf-8"))
    data["source"] = "missing"
    data["source_sha256"] = "abc"
    mp.write_text(json.dumps(data), encoding="utf-8")
    assert not integrity.artifact_valid(p)


def test_config_validation_invalid_branches():
    base = {
        "pipeline": {"seed": 1, "resume": True},
        "stages": {x: True for x in config_validation.STAGES},
        "crawl": {"sources": {"web": {}}, "web": {}},
        "clean": {},
        "embed_dedup": {},
        "weight": {},
        "tokenizer": {"vocab_size": 100, "train_on_sample": True},
        "shard": {"sequence_length": 8, "shard_size_tokens": 9, "val_fraction": 0.1, "dtype": "uint16"},
        "train": {"vocab_size": 100, "seq_len": 8, "total_steps": 10, "batch_size": 1, "grad_accum_steps": 1, "eval_every_steps": 1, "eval_batches": 1, "checkpoint_every_steps": 1, "keep_checkpoints": 1, "model_preset": "85M", "resume": True, "allow_cpu_training": True, "auto_size": False, "warmup_steps": 1},
        "export": {"quant": "F16", "llamacpp_dir": "third_party/llama.cpp"},
    }
    config_validation.validate_config(base)
    cases = [
        ("pipeline.seed", lambda c: c["pipeline"].update(seed=True)),
        ("resume", lambda c: c["pipeline"].update(resume="x")),
        ("stage", lambda c: c["stages"].update(crawl="x")),
        ("top", lambda c: c.update(unknown={})),
        ("nested", lambda c: c["crawl"]["web"].update(bad=True)),
        ("vocab", lambda c: c["tokenizer"].update(vocab_size=0)),
        ("vocab_match", lambda c: c["train"].update(vocab_size=101)),
        ("seq", lambda c: c["shard"].update(sequence_length=0)),
        ("seq_match", lambda c: c["train"].update(seq_len=9)),
        ("dtype", lambda c: c.update({"tokenizer": {**c["tokenizer"], "vocab_size": 70000}})),
        ("shard_size", lambda c: c["shard"].update(shard_size_tokens=8)),
        ("val", lambda c: c["shard"].update(val_fraction=1)),
        ("steps", lambda c: c["train"].update(total_steps=0)),
        ("batch", lambda c: c["train"].update(batch_size=0)),
        ("preset", lambda c: c["train"].update(model_preset="bad")),
        ("hours", lambda c: c["train"].update(target_training_hours=0)),
        ("warmup", lambda c: c["train"].update(warmup_steps=10)),
        ("quant", lambda c: c["export"].update(quant="bad")),
        ("llama", lambda c: c["export"].update(llamacpp_dir=" ")),
    ]
    for _, mutate in cases:
        cfg = json.loads(json.dumps(base))
        mutate(cfg)
        with pytest.raises(ValueError):
            config_validation.validate_config(cfg)


def test_doctor_helpers(monkeypatch, tmp_path):
    assert doctor._check("x", 1, "d")["ok"]
    monkeypatch.setattr(doctor.sys, "version_info", (3, 12))
    assert doctor._python_ok()
    assert "requires Python" in doctor._python_detail()
    p = tmp_path / "dir"
    p.mkdir()
    assert doctor._writable(p)
    monkeypatch.setattr(doctor.importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("nope")))
    assert doctor._torch_state()[0] is False
    assert doctor._semantic_dedup_state()[0] is False
    monkeypatch.setattr(doctor.importlib, "import_module", lambda name: SimpleNamespace(__version__="test", cuda=SimpleNamespace(is_available=lambda: False)))
    assert doctor._semantic_dedup_state()[0]
    target = tmp_path / "third_party" / "llama.cpp"
    target.mkdir(parents=True)
    assert doctor._llamacpp_state(tmp_path)[0] is False
    (target / ".git").mkdir()
    (target / "convert_hf_to_gguf.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=doctor.LLAMACPP_COMMIT + "abc"))
    monkeypatch.setattr(doctor.os, "access", lambda p, mode: True)
    (target / "llama-quantize").write_text("", encoding="utf-8")
    assert doctor._llamacpp_state(tmp_path)[0]
    ok, checks = doctor.run_doctor(tmp_path)
    assert isinstance(ok, bool) and checks


def test_trainer_math_rng_and_checkpoint(tmp_path, monkeypatch):
    assert cosine_lr(0, 10, 1e-3, 1e-4, 100) == 0
    assert cosine_lr(20, 10, 1e-3, 1e-4, 100) < 1e-3
    assert cosine_lr(100, 10, 1e-3, 1e-4, 100) == 1e-4
    _seed_everything(7)
    state = _rng_state()
    _seed_everything(8)
    _restore_rng_state(state)

    cfg = ModelConfig(vocab_size=13, seq_len=4, n_layers=1, n_heads=1, n_kv_heads=1, d_model=8, d_ffn=16)
    model = LlamaModel(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cpu", enabled=False)
    provenance = {"x": "y"}
    out = tmp_path / "checkpoints"
    path = save_checkpoint(model, optimizer, scaler, 3, 1.25, {"seed": 7}, out, provenance=provenance)
    assert latest_checkpoint(out) == path
    assert load_checkpoint(path, model, optimizer, scaler, torch.device("cpu"), expected_provenance=provenance) == 3

    payload = json.loads((path.with_name(path.name + ".manifest.json")).read_text(encoding="utf-8"))
    payload["sha256"] = "bad"
    path.with_name(path.name + ".manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_checkpoint(path, model)

    assert latest_checkpoint(tmp_path / "missing") is None


def test_trainer_validation_and_prune(tmp_path):
    trainer = Trainer({"pipeline": {"output_dir": str(tmp_path)}})
    assert trainer.ckpt_dir == tmp_path / "checkpoints"
    assert trainer.log_path.parent.is_dir()
    with pytest.raises(RuntimeError):
        trainer.run()
    trainer.ckpt_dir.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        p = trainer.ckpt_dir / f"ckpt_{i:07d}.pt"
        p.write_bytes(b"x")
    trainer._prune_checkpoints(trainer.ckpt_dir, keep=2)
    assert not (trainer.ckpt_dir / "ckpt_0000000.pt").exists()
    assert (trainer.ckpt_dir / "ckpt_0000003.pt").exists()


def test_provenance_requires_manifests(tmp_path):
    model_cfg = ModelConfig(vocab_size=8, seq_len=4, n_layers=1, n_heads=1, n_kv_heads=1, d_model=8, d_ffn=8)
    cfg = {"_pipeline_config_sha256": "abc", "pipeline": {"output_dir": str(tmp_path)}}
    with pytest.raises(RuntimeError):
        _provenance(cfg, model_cfg, tmp_path / "shards")

def test_integrity_validate_checkpoint_and_atomic_cleanup(tmp_path):
    cfg = ModelConfig(vocab_size=8, seq_len=4, n_layers=1, n_heads=1, n_kv_heads=1, d_model=8, d_ffn=8)
    model = LlamaModel(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cpu", enabled=False)
    path = save_checkpoint(model, opt, scaler, 2, 0.5, {"seed": 1}, tmp_path)
    assert integrity.validate_checkpoint(path, expected_config=cfg.to_dict())["step"] == 2
    with pytest.raises(RuntimeError):
        integrity.validate_checkpoint(path, expected_config={**cfg.to_dict(), "seq_len": 9})
    mp = integrity.manifest_path(path)
    meta = json.loads(mp.read_text(encoding="utf-8"))
    meta["kind"] = "wrong"
    mp.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(RuntimeError):
        integrity.validate_checkpoint(path)

def test_integrity_checkpoint_state_failures(tmp_path):
    cfg = ModelConfig(vocab_size=8, seq_len=4, n_layers=1, n_heads=1, n_kv_heads=1, d_model=8, d_ffn=8)
    model = LlamaModel(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cpu", enabled=False)
    path = save_checkpoint(model, opt, scaler, 1, 0.5, {}, tmp_path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    payload["model_cfg"]["d_model"] = 16
    torch.save(payload, path)
    integrity.write_manifest(path, kind="checkpoint")
    with pytest.raises(RuntimeError):
        integrity.validate_checkpoint(path)
    payload["model_cfg"] = cfg.to_dict()
    payload["model"] = []
    torch.save(payload, path)
    integrity.write_manifest(path, kind="checkpoint")
    with pytest.raises(RuntimeError):
        integrity.validate_checkpoint(path)

def test_config_catalog_branches(monkeypatch):
    groups = [{"id": "a"}, {"id": "b"}]
    profiles = [{"dataset_id": 1, "group_id": "a"}, {"dataset_id": 2, "group_id": "b"}]
    monkeypatch.setattr(cc_config, "load_groups", lambda: groups)
    monkeypatch.setattr(cc_config, "load_profiles", lambda: profiles)
    assert cc_config.validate_profile_catalog() == {1: profiles[0], 2: profiles[1]}
    assert cc_config.profile_by_id(2) == profiles[1]
    assert cc_config.profile_by_group_id("a") == profiles[0]
    assert cc_config.group_by_id("b") == groups[1]
    for bad in [
        [{"dataset_id": "x", "group_id": "a"}],
        [{"dataset_id": 0, "group_id": "a"}],
        [{"dataset_id": 1, "group_id": "missing"}],
        [{"dataset_id": 1, "group_id": "a"}, {"dataset_id": 1, "group_id": "b"}],
        [{"dataset_id": 1, "group_id": "a"}, {"dataset_id": 3, "group_id": "b"}],
        [{"dataset_id": 1, "group_id": "a"}, {"dataset_id": 2, "group_id": "a"}],
    ]:
        monkeypatch.setattr(cc_config, "load_profiles", lambda bad=bad: bad)
        with pytest.raises(ValueError):
            cc_config.validate_profile_catalog()

def test_command_center_web_contracts(monkeypatch):
    assert "M²S Model Training Pipeline" in cc_web.index().body.decode()
    system = cc_web.system()
    assert system["security"]["api_access"] == "localhost-only"
    assert cc_web._safe_error(FileNotFoundError("x")).status_code == 404
    assert cc_web._safe_error(ValueError("x")).status_code == 400
    assert cc_web._safe_error(RuntimeError("x")).status_code == 500
    assert cc_web._safe_error(ValueError("x"), code="BAD").detail["code"] == "BAD"
    monkeypatch.setattr(cc_web, "status", lambda did=None: {"id": did} if did is not None else {"items": []})
    monkeypatch.setattr(cc_web.store, "tail_events", lambda did: [{"event": did}])
    assert cc_web.dataset(4)["events"] == [{"event": 4}]
    monkeypatch.setattr(cc_web, "status", lambda did=None: None)
    with pytest.raises(HTTPException):
        cc_web.dataset(4)
    monkeypatch.setattr(cc_web, "add", lambda *a: {"created": a[0]})
    assert cc_web.create(cc_web.DatasetCreate(name="n"))["created"] == "n"
    monkeypatch.setattr(cc_web, "add", lambda *a: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(HTTPException):
        cc_web.create(cc_web.DatasetCreate(name="n"))
    monkeypatch.setattr(cc_web, "groups", lambda: ["g"])
    assert cc_web.api_groups() == ["g"]
    monkeypatch.setattr(cc_web, "credential_list", lambda: ["c"])
    assert cc_web.creds() == ["c"]
    monkeypatch.setattr(cc_web, "credential_set", lambda *a: {"name": a[0]})
    assert cc_web.set_cred(cc_web.CredentialSet(name="n", secret="s"))["name"] == "n"
    monkeypatch.setattr(cc_web, "credential_delete", lambda name: name)
    assert cc_web.del_cred("n") == {"deleted": "n"}

def test_command_center_middleware_security():
    from starlette.requests import Request
    import asyncio
    async def call_next(request):
        return cc_web.JSONResponse(status_code=200, content={"ok": True})
    async def run(headers, method="GET", path="/api/system", host="127.0.0.1"):
        scope = {"type": "http", "method": method, "path": path, "headers": [(k.encode(), v.encode()) for k, v in headers.items()], "client": (host, 1234), "scheme": "http", "server": ("127.0.0.1", 80), "query_string": b"", "root_path": "", "http_version": "1.1"}
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}
        return await cc_web.LocalhostOnlyMiddleware(cc_web.app).dispatch(Request(scope, receive), call_next)
    assert asyncio.run(run({"content-length": str(cc_web.MAX_REQUEST_BYTES + 1)})).status_code == 413
    assert asyncio.run(run({"content-length": "bad"})).status_code == 400
    assert asyncio.run(run({}, host="10.0.0.2")).status_code == 403
    assert asyncio.run(run({"origin": "https://evil.test", cc_web.CONTROL_HEADER: "1"}, method="POST")).status_code == 403
    assert asyncio.run(run({}, method="POST")).status_code == 403
    assert asyncio.run(run({cc_web.CONTROL_HEADER: "1"}, method="POST")).status_code == 200
    assert asyncio.run(run({}, path="/health")).status_code == 200

def test_semantic_dedup_fallback_and_embedding_paths(monkeypatch):
    docs = [
        Document("1", text="alpha beta gamma", final_weight=1.0),
        Document("2", text="alpha beta gamma", final_weight=2.0),
        Document("3", text="unique words here", final_weight=1.0),
    ]
    d = semantic_dedup.SemanticDeduplicator({"mode": "fallback", "similarity_threshold": 0.8})
    assert d.run([]) == []
    kept = d.run(docs)
    assert [x.doc_id for x in kept] == ["2", "3"]
    assert list(d.stream(iter(docs), buffer_size=2))[0].doc_id == "2"
    with pytest.raises(ValueError):
        list(d.stream(iter(docs), buffer_size=0))
    assert semantic_dedup.SemanticDeduplicator._fallback_similarity("", "x") == 0.0
    assert semantic_dedup._cosine_brute(np.eye(2, dtype=np.float32), np.array([1.0, 0.0], dtype=np.float32), 1)[1][0] == 0
    monkeypatch.setattr(semantic_dedup, "ST_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="dependencies"):
        semantic_dedup.SemanticDeduplicator({"mode": "embedding"})._ensure_embedding_or_fallback()
    monkeypatch.setattr(semantic_dedup, "ST_AVAILABLE", True)
    monkeypatch.setattr(semantic_dedup, "FAISS_AVAILABLE", True)
    class FakeModel:
        def get_sentence_embedding_dimension(self): return 2
        def encode(self, chunks, **kwargs): return np.array([[1, 0] for _ in chunks], dtype=np.float32)
    monkeypatch.setattr(semantic_dedup, "SentenceTransformer", lambda *a, **k: FakeModel())
    emb = semantic_dedup.SemanticDeduplicator({"mode": "embedding", "model_path": "local"})
    emb._load_model()
    assert emb._dim == 2
    assert emb._embed(["abc"])[0].tolist() == [1.0, 0.0]

def test_orchestrator_helpers_and_manifest_validation(tmp_path, monkeypatch):
    cfg = {"crawl": {"sources": {"web": True, "github": True, "arxiv": False, "huggingface": True}, "web": {"seed_urls": ["https://a"]}}}
    groups_path = tmp_path / "groups.yaml"
    groups_path.write_text("dataset_groups:\n  - id: g1\n    sources: {web: true, github: true, huggingface: true}\n    huggingface:\n      datasets: [{repo: org/data, config: c, split: train}]\n    google:\n      queries: [ml]\n", encoding="utf-8")
    paths = {"dataset_groups": groups_path}
    sources = orchestrator._manifest_sources(cfg, paths)
    assert any(x["kind"] == "huggingface" for x in sources)
    with pytest.raises(ValueError):
        orchestrator._manifest_sources(cfg, paths, "missing")
    assert orchestrator._source_entry("web", "u", "g")["license"] == "unknown"
    root = tmp_path
    (root / "config").mkdir()
    for name in ["pipeline_config.yaml", "source_weights.yaml", "dataset_groups.yaml", "dataset_profiles.yaml"]:
        (root / "config" / name).write_text(name, encoding="utf-8")
    sp = orchestrator._source_definition_paths({"crawl": {}}, root)
    assert set(sp) == {"pipeline_config", "source_weights", "dataset_groups", "dataset_profiles"}
    assert all(p.is_file() for p in sp.values())
    out = tmp_path / "manifest.json"
    monkeypatch.setattr(orchestrator, "PROJECT_ROOT", tmp_path)
    orchestrator._write_source_manifest(out, cfg, sp, selected_group_id="all", retrieval_started_at="s", retrieval_completed_at="e")
    assert orchestrator._source_manifest_is_valid(out, "all", sp)
    data = json.loads(out.read_text(encoding="utf-8"))
    data["sources"][0]["raw_source_sha256"] = "bad"
    out.write_text(json.dumps(data), encoding="utf-8")
    assert not orchestrator._source_manifest_is_valid(out)

def test_orchestrator_jsonl_and_pipeline_run_dispatch(tmp_path, monkeypatch):
    good = tmp_path / "good.jsonl"
    good.write_text(json.dumps(Document("1", text="hello").to_jsonl()) + "\n\n", encoding="utf-8")
    assert [d.doc_id for d in orchestrator._jsonl_read(good)] == ["1"]
    bad = tmp_path / "bad.jsonl"
    bad.write_text('"not an object"\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        list(orchestrator._jsonl_read(bad))
    p = object.__new__(orchestrator.Pipeline)
    p.cfg = {"stages": {"clean": True}, "pipeline": {}}
    p._scratch = tmp_path
    p._resume = False
    calls = []
    monkeypatch.setattr(p, "stage_clean", lambda path: calls.append(("clean", path)) or tmp_path / "clean")
    assert p.run("clean") == {"clean": tmp_path / "clean"}
    assert calls == [("clean", tmp_path / "01_crawled.jsonl")]
    with pytest.raises(ValueError):
        p.run("unknown")
    p.cfg = {"stages": {}}
    with pytest.raises(ValueError):
        p.run("all")

def test_trainer_checkpoint_resume_guards(tmp_path):
    cfg = ModelConfig(vocab_size=8, seq_len=4, n_layers=1, n_heads=1, n_kv_heads=1, d_model=8, d_ffn=8)
    model = LlamaModel(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    scaler = torch.amp.GradScaler("cpu", enabled=False)
    path = save_checkpoint(model, opt, scaler, 2, 0.4, {"seed": 1}, tmp_path, provenance={"p": 1})
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        load_checkpoint(path, model, opt, scaler, torch.device("cpu"), expected_provenance={"p": 2})
    payload = torch.load(path, map_location="cpu", weights_only=False)
    payload.pop("rng_state")
    torch.save(payload, path)
    integrity.write_manifest(path, kind="checkpoint", provenance={"p": 1})
    with pytest.raises(RuntimeError, match="RNG state"):
        load_checkpoint(path, model)
    payload["rng_state"] = _rng_state()
    payload["loader_state"] = {"train": None, "val": None}
    torch.save(payload, path)
    integrity.write_manifest(path, kind="checkpoint", provenance={"p": 1})
    class Loader:
        def load_state_dict(self, state):
            self.state = state
    with pytest.raises(RuntimeError, match="train loader state"):
        load_checkpoint(path, model, train_loader=Loader())
    (tmp_path / "ckpt_0000002.pt").write_bytes(b"x" * 1024)
    assert latest_checkpoint(tmp_path) is None
    (tmp_path / "ckpt_0000003.pt").write_bytes(b"x" * 1024)
    (tmp_path / "ckpt_0000003.pt.manifest.json").write_text("{}", encoding="utf-8")
    assert latest_checkpoint(tmp_path) is None


def test_trainer_cpu_guard_and_seq_len_guard(monkeypatch, tmp_path):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    trainer = Trainer({"pipeline": {"output_dir": str(tmp_path)}, "train": {"allow_cpu_training": False}})
    with pytest.raises(RuntimeError, match="allow_cpu_training"):
        trainer.run()
    cfg = {
        "pipeline": {"output_dir": str(tmp_path)},
        "train": {
            "allow_cpu_training": True, "auto_size": False, "model_preset": "85M",
            "vocab_size": 8, "seq_len": 8, "total_steps": 1, "warmup_steps": 1,
            "batch_size": 1, "grad_accum_steps": 1, "eval_every_steps": 1,
            "eval_batches": 1, "checkpoint_every_steps": 1, "shard_dir": str(tmp_path / "shards")
        },
        "shard": {"sequence_length": 4, "dtype": "uint16"},
        "_pipeline_config_sha256": "test",
    }
    with pytest.raises(RuntimeError, match="exceeds shard sequence_length"):
        Trainer(cfg).run()


def test_trainer_auto_size_fallback_and_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    class Hardware:
        def to_dict(self): return {"tier": "cpu"}
    class Profile:
        model_preset = "85M"; seq_len = 4; batch_size = 1; grad_accum_steps = 1
        eval_batches = 1; eval_every_steps = 1; checkpoint_every_steps = 1; recommended_steps = 1
        def to_dict(self): return {"model_preset": self.model_preset}
    monkeypatch.setattr("pipeline.trainer.train.profile_hardware", lambda: Hardware())
    monkeypatch.setattr("pipeline.trainer.train.estimate_total_tokens", lambda p: (_ for _ in ()).throw(ValueError("bad shard")))
    monkeypatch.setattr("pipeline.trainer.train.recommend_training_profile", lambda **kwargs: Profile())
    cfg = {
        "pipeline": {"output_dir": str(tmp_path)},
        "train": {"allow_cpu_training": True, "auto_size": True, "model_preset": "85M", "vocab_size": 8, "seq_len": 4, "total_steps": 1, "target_training_hours": None, "observed_tokens_per_sec": None},
        "shard": {"sequence_length": 4},
        "_pipeline_config_sha256": "test",
    }
    with pytest.raises(RuntimeError, match="Training provenance"):
        Trainer(cfg).run()
