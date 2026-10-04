from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import orchestrator
from pipeline.types import Document


def _bare_pipeline(tmp_path):
    p = object.__new__(orchestrator.Pipeline)
    p.cfg = {
        "crawl": {
            "sources": {"web": True, "github": True, "arxiv": False, "huggingface": True, "google": True},
            "web": {"seed_urls": ["https://seed.example"]},
        },
        "embed_dedup": {"buffer_size": 2},
        "weight": {"config_file": "config/source_weights.yaml", "strategy": "upsample"},
        "tokenizer": {"output_path": str(tmp_path / "tokenizer")},
        "shard": {"output_dir": str(tmp_path / "shards"), "sequence_length": 4},
        "train": {"allow_cpu_training": True},
        "export": {"llamacpp_dir": "third_party/llama.cpp", "quant": "q4_k_m", "model_name": "m"},
        "pipeline": {"output_dir": str(tmp_path / "output")},
    }
    p._scratch = tmp_path / "scratch"
    p._out = tmp_path / "output"
    p._scratch.mkdir()
    p._out.mkdir()
    p._resume = False
    p._config_sha256 = "cfg"
    p._weights_path = tmp_path / "weights.yaml"
    p._dataset_groups_path = tmp_path / "groups.yaml"
    p._clean_config_path = tmp_path / "cleaner.yaml"
    for path in (p._weights_path, p._dataset_groups_path, p._clean_config_path):
        path.write_text("x", encoding="utf-8")
    p._source_definition_paths = {}
    p._source_manifest_path = tmp_path / "source_manifest.json"
    p._weights = SimpleNamespace()
    p._signals = SimpleNamespace()
    p._dataset_root = None
    p.dataset_id = None
    p._provenance = lambda stage, input_path=None, extra=None: {"stage": stage}
    return p


def test_orchestrator_source_manifest_validation_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "source.yaml"
    source.write_text("x", encoding="utf-8")
    paths = {"pipeline_config": source}
    cfg = {"crawl": {"sources": {"web": True}, "web": {"seed_urls": ["https://a"]}}}
    out = tmp_path / "manifest.json"
    orchestrator._write_source_manifest(
        out, cfg, paths, selected_group_id="g1",
        retrieval_started_at="s", retrieval_completed_at="e",
    )
    assert orchestrator._source_manifest_is_valid(out, "g1", paths)
    assert not orchestrator._source_manifest_is_valid(out, "g2", paths)

    data = json.loads(out.read_text(encoding="utf-8"))
    data["source_definition_files"]["pipeline_config"]["sha256"] = "z" * 63
    out.write_text(json.dumps(data), encoding="utf-8")
    assert not orchestrator._source_manifest_is_valid(out)

    orchestrator._write_source_manifest(out, cfg, paths, selected_group_id="g1", retrieval_started_at="s", retrieval_completed_at="e")
    data = json.loads(out.read_text(encoding="utf-8"))
    data["sources"][0]["dataset_group"] = "other"
    out.write_text(json.dumps(data), encoding="utf-8")
    assert not orchestrator._source_manifest_is_valid(out)

    orchestrator._write_source_manifest(out, cfg, paths, selected_group_id="g1", retrieval_started_at="s", retrieval_completed_at="e")
    data = json.loads(out.read_text(encoding="utf-8"))
    data["sources"][0]["raw_source_sha256"] = 123
    out.write_text(json.dumps(data), encoding="utf-8")
    assert not orchestrator._source_manifest_is_valid(out)

    assert orchestrator._file_hash(tmp_path / "missing") is None
    assert len(orchestrator._hash_value({"b": 2, "a": 1})) == 64


def test_orchestrator_crawl_groups_and_failure_paths(tmp_path, monkeypatch):
    p = _bare_pipeline(tmp_path)
    groups = [
        {
            "id": "g1",
            "sources": {"web": True, "github": True, "arxiv": True, "huggingface": True, "google": True},
            "web": {"seed_urls": ["https://g1"]},
            "github": {}, "arxiv": {}, "huggingface": {}, "google": {},
        },
        {"id": "g2", "sources": {"web": False, "github": False, "arxiv": False, "huggingface": False, "google": False}},
    ]
    p._load_dataset_groups = lambda: groups
    crawler_calls = []

    class Crawler:
        def __init__(self, cfg, weights, signals):
            crawler_calls.append((cfg["sources"], cfg.get("web", {}).get("seed_urls")))
        def crawl(self):
            yield Document(f"d{len(crawler_calls)}", text="doc")

    monkeypatch.setattr(orchestrator, "_load_class", lambda module, name: Crawler)
    monkeypatch.setattr(orchestrator, "atomic_jsonl_write", lambda path, producer: sum(1 for _ in producer()))
    monkeypatch.setattr(orchestrator, "write_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(orchestrator, "_write_source_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(p, "_should_skip", lambda *args, **kwargs: False)

    out = p.stage_crawl(only_group="g1")
    assert out.name == "01_crawled__g1.jsonl"
    assert len(crawler_calls) == 5

    with pytest.raises(ValueError, match="Unknown dataset group"):
        p.stage_crawl(only_group="missing")

    p._load_dataset_groups = lambda: [{"id": "empty", "sources": {k: False for k in orchestrator.SOURCE_KINDS}}]
    with pytest.raises(RuntimeError, match="no documents"):
        p.stage_crawl(only_group="empty")


def test_orchestrator_stage_skip_and_input_guards(tmp_path, monkeypatch):
    p = _bare_pipeline(tmp_path)
    missing = tmp_path / "missing.jsonl"
    monkeypatch.setattr(p, "_should_skip", lambda *args, **kwargs: True)
    assert p.stage_clean(missing) == p._scratch / "02_cleaned.jsonl"
    assert p.stage_embed_dedup(missing) == p._scratch / "03_deduped.jsonl"
    assert p.stage_weight(missing) == p._scratch / "04_weighted.jsonl"

    monkeypatch.setattr(p, "_should_skip", lambda *args, **kwargs: False)
    monkeypatch.setattr(orchestrator, "artifact_valid", lambda path, *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="Clean input"):
        p.stage_clean(missing)
    with pytest.raises(RuntimeError, match="Dedup input"):
        p.stage_embed_dedup(missing)
    with pytest.raises(RuntimeError, match="Weight input"):
        p.stage_weight(missing)
    with pytest.raises(RuntimeError, match="Tokenizer input"):
        p.stage_tokenize(missing)

    marker = Path(p.cfg["tokenizer"]["output_path"]) / "tokenizer.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(p, "_should_skip", lambda *args, **kwargs: True)

    class TokenTrainer:
        def __init__(self, cfg):
            self.cfg = cfg
        def load(self):
            return "loaded"

    monkeypatch.setattr(orchestrator, "_load_class", lambda module, name: TokenTrainer)
    assert p.stage_tokenize(missing) == "loaded"


def test_orchestrator_shard_resume_rebuild_and_run_dispatch(tmp_path, monkeypatch):
    p = _bare_pipeline(tmp_path)
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("{}\n", encoding="utf-8")
    tokenizer = SimpleNamespace(get_vocab_size=lambda: 8)
    shard_dir = Path(p.cfg["shard"]["output_dir"])
    marker = shard_dir / "shards.manifest.json"
    shard_dir.mkdir(parents=True)
    shard = shard_dir / "shard_000.bin"
    shard.write_bytes(b"x")

    provenance = {"stage": "shard"}
    p._provenance = lambda *args, **kwargs: provenance
    marker.write_text(json.dumps({
        "provenance": provenance,
        "files": [{"name": shard.name, "size": 1, "sha256": orchestrator.sha256_file(shard)}],
    }), encoding="utf-8")
    p._resume = True
    assert p.stage_shard(corpus, tokenizer) == shard_dir

    marker.write_text("{", encoding="utf-8")
    writes = []

    class Writer:
        def __init__(self, cfg, tok):
            self.cfg = cfg
            writes.append(("init", cfg["sequence_length"], tok))
        def write(self, path):
            writes.append(("write", path))
            output_dir = Path(self.cfg.get("output_dir", shard_dir))
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "shard_001.bin").write_bytes(b"y")

    monkeypatch.setattr(orchestrator, "_load_class", lambda module, name: Writer)
    assert p.stage_shard(corpus, tokenizer) == shard_dir
    assert writes and writes[-1][0] == "write"

    class NoOutputWriter:
        def __init__(self, cfg, tok):
            pass
        def write(self, path):
            return None

    monkeypatch.setattr(orchestrator, "_load_class", lambda module, name: NoOutputWriter)
    for path in shard_dir.glob("shard_*.bin"):
        path.unlink()
    with pytest.raises(RuntimeError, match="no shard files"):
        p.stage_shard(corpus, tokenizer)

    calls = []
    p.cfg["stages"] = {name: True for name in ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]}
    p.stage_crawl = lambda group=None: calls.append("crawl") or tmp_path / "crawl"
    p.stage_clean = lambda path: calls.append("clean") or tmp_path / "clean"
    p.stage_embed_dedup = lambda path: calls.append("dedup") or tmp_path / "dedup"
    p.stage_weight = lambda path: calls.append("weight") or tmp_path / "weight"
    p.stage_tokenize = lambda path: calls.append("tokenize") or tokenizer
    p.stage_shard = lambda path, tok: calls.append("shard") or shard_dir
    p.stage_train = lambda: calls.append("train") or tmp_path / "checkpoint"
    p.stage_export = lambda: calls.append("export") or "exported"
    assert p.run("all", dataset_group="g1")["export"] == "exported"
    assert calls == ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]
