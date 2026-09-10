from __future__ import annotations

import json
from pathlib import Path

import yaml

from pipeline.orchestrator import (
    _implementation_sha256,
    _source_definition_paths,
    _source_manifest_is_valid,
    _write_source_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_source_definition_hashes_include_seed_urls():
    cfg = yaml.safe_load((ROOT / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    paths = _source_definition_paths(cfg, ROOT)
    assert "seed_urls" in paths
    assert paths["seed_urls"].is_file()


def test_source_definition_paths_bind_to_selected_config():
    cfg = yaml.safe_load((ROOT / "config" / "pipeline_config.smoke.yaml").read_text(encoding="utf-8"))
    cfg["_pipeline_config_path"] = str(ROOT / "config" / "pipeline_config.smoke.yaml")
    paths = _source_definition_paths(cfg, ROOT)
    assert paths["pipeline_config"] == (ROOT / "config" / "pipeline_config.smoke.yaml").resolve()


def test_source_manifest_records_complete_release_metadata(tmp_path):
    cfg = yaml.safe_load((ROOT / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    cfg["_pipeline_config_path"] = str(ROOT / "config" / "pipeline_config.yaml")
    paths = _source_definition_paths(cfg, ROOT)
    target = tmp_path / "source_manifest.json"
    _write_source_manifest(
        target,
        cfg,
        paths,
        retrieval_started_at="2026-01-01T00:00:00+00:00",
        retrieval_completed_at="2026-01-01T00:01:00+00:00",
    )
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["retrieval_started_at"]
    assert data["retrieval_completed_at"]
    assert data["source_definition_files"]["pipeline_config"]["sha256"]
    assert data["sources"]
    assert {source["kind"] for source in data["sources"]} == {"web", "github", "arxiv", "huggingface", "google"}
    assert all({"kind", "identifier", "revision", "license", "raw_source_sha256"} <= set(source) for source in data["sources"])
    assert _source_manifest_is_valid(target)


def test_source_manifest_validation_rejects_incomplete_manifest(tmp_path):
    target = tmp_path / "source_manifest.json"
    target.write_text(json.dumps({"schema": 1, "sources": []}), encoding="utf-8")
    assert not _source_manifest_is_valid(target)


def test_stage_implementation_identity_is_nonempty():
    digest = _implementation_sha256("clean")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
