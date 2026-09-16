from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pipeline.trainer.model import ModelConfig
from pipeline.trainer.train import _provenance
from scripts.export_gguf import _enforce_training_provenance


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_manifest(path: Path) -> None:
    path.write_text(json.dumps({"schema": 2, "dataset_group": "fixture", "retrieval_started_at": "t", "retrieval_completed_at": "t", "source_definition_files": {}, "sources": [{"kind": "local", "identifier": "fixture", "revision": "embedded", "license": "test", "raw_source_sha256": None, "dataset_group": "fixture"}], "rights_note": "test"}), encoding="utf-8")


def test_training_provenance_binds_source_manifest(tmp_path):
    output = tmp_path / "output"; output.mkdir(); _source_manifest(tmp_path / "source_manifest.json")
    shards = output / "shards"; shards.mkdir()
    cfg = {"_pipeline_config_sha256": "a" * 64, "pipeline": {"output_dir": str(output)}}
    with pytest.raises(RuntimeError, match="shard manifest"):
        _provenance(cfg, ModelConfig(vocab_size=8, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=8), shards)


def test_training_provenance_records_source_manifest_hash(tmp_path):
    output = tmp_path / "output"; output.mkdir(); source = tmp_path / "source_manifest.json"; _source_manifest(source)
    shards = output / "shards"; shards.mkdir(); (shards / "shards.manifest.json").write_text("{}", encoding="utf-8")
    cfg = {"_pipeline_config_sha256": "a" * 64, "pipeline": {"output_dir": str(output)}}
    provenance = _provenance(cfg, ModelConfig(vocab_size=8, d_model=16, n_layers=1, n_heads=4, n_kv_heads=4, d_ffn=32, seq_len=8), shards)
    assert provenance["schema"] == 2
    assert provenance["source_manifest_sha256"] == _sha256(source)


def test_export_provenance_rejects_source_manifest_replacement(tmp_path):
    output = tmp_path / "output"; (output / "shards").mkdir(parents=True); (output / "tokenizer").mkdir(parents=True); (tmp_path / "scratch").mkdir(); source = tmp_path / "source_manifest.json"; _source_manifest(source)
    for path, payload in ((output / "shards" / "shards.manifest.json", {"provenance": {"pipeline_config_sha256": "a"}}), (output / "tokenizer" / "tokenizer.json.manifest.json", {"provenance": {"pipeline_config_sha256": "a"}}), (tmp_path / "scratch" / "04_weighted.jsonl.manifest.json", {"provenance": {"pipeline_config_sha256": "a"}})):
        path.write_text(json.dumps(payload), encoding="utf-8")
    provenance = {"schema": 2, "pipeline_config_sha256": "a", "train_config_sha256": "b", "model_config_sha256": "c", "shard_manifest_sha256": _sha256(output / "shards" / "shards.manifest.json"), "source_manifest_sha256": "wrong", "seed": 42}
    with pytest.raises(RuntimeError, match="source-manifest identity"):
        _enforce_training_provenance(output, {"provenance": provenance, "model_cfg": {"vocab_size": 8}})
