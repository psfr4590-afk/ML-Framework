from __future__ import annotations

import json
from pathlib import Path

import yaml

from pipeline.orchestrator import _implementation_sha256, _source_definition_paths, _write_source_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_source_definition_hashes_include_seed_urls():
    cfg = yaml.safe_load((ROOT / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    paths = _source_definition_paths(cfg, ROOT)
    assert "seed_urls" in paths
    assert paths["seed_urls"].is_file()


def test_source_manifest_records_definition_hashes(tmp_path):
    cfg = yaml.safe_load((ROOT / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    paths = _source_definition_paths(cfg, ROOT)
    target = tmp_path / "source_manifest.json"
    _write_source_manifest(target, cfg, paths)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["source_definition_files"]["seed_urls"]["sha256"]
    assert data["sources"]


def test_stage_implementation_identity_is_nonempty():
    digest = _implementation_sha256("clean")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
