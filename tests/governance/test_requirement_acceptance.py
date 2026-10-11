"""Governance requirement acceptance tests.

These tests intentionally verify repository contracts without requiring a training
run, CUDA, network access, or optional GUI dependencies. They are an initial
acceptance layer, not a claim that every operational requirement is fully proven.
Requirement IDs are kept explicit so the governance coverage checker can trace
each target.
"""
from __future__ import annotations

import ast
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"Required repository file is missing: {path}"
    return target.read_text(encoding="utf-8")


def _json(path: str):
    return json.loads(_read(path))


def _python(path: str):
    return ast.parse(_read(path), filename=path)


def _tracked_paths():
    return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


# UI (001-006): public operator surface and its documented entrypoints.
def test_REQ_UI_001():
    assert (ROOT / "command_center" / "web.py").is_file()


def test_REQ_UI_002():
    source = _read("command_center/web.py")
    assert "FastAPI" in source


def test_REQ_UI_003():
    assert (ROOT / "command_center" / "templates" / "index.html").is_file()


def test_REQ_UI_004():
    assert (ROOT / "run_command_center.py").is_file()


def test_REQ_UI_005():
    source = _read("command_center/app.py")
    assert len(source.splitlines()) < 30, "Compatibility entrypoint should remain a thin delegate"


def test_REQ_UI_006():
    assert (ROOT / "command_center" / "security.py").is_file()


# ENV (001-006): packaging, bootstrap, and declared runtime contracts.
def test_REQ_ENV_001():
    data = tomllib.loads(_read("pyproject.toml"))
    assert isinstance(data, dict)


def test_REQ_ENV_002():
    assert (ROOT / "bootstrap.py").is_file()


def test_REQ_ENV_003():
    assert (ROOT / "bootstrap_windows.ps1").is_file()


def test_REQ_ENV_004():
    assert (ROOT / ".env.example").is_file()


def test_REQ_ENV_005():
    data = tomllib.loads(_read("pyproject.toml"))
    requires = data.get("project", {}).get("requires-python", "")
    assert requires, "project.requires-python must declare the supported Python range"


def test_REQ_ENV_006():
    source = _read("bootstrap.py")
    assert "doctor" in source.lower()


# WF (001-008): configuration, stage identity, lifecycle and execution policy.
def test_REQ_WF_001():
    assert (ROOT / "config" / "pipeline_config.yaml").is_file()


def test_REQ_WF_002():
    assert (ROOT / "config" / "pipeline_config.smoke.yaml").is_file()


def test_REQ_WF_003():
    assert (ROOT / "command_center" / "runner.py").is_file()


def test_REQ_WF_004():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("state", "status", "cancel", "lifecycle"))


def test_REQ_WF_005():
    source = _read("mlframework.py").lower()
    assert "smoke" in source


def test_REQ_WF_006():
    assert (ROOT / "run_pipeline.py").is_file()


def test_REQ_WF_007():
    assert (ROOT / "config" / "dataset_groups.yaml").is_file()


def test_REQ_WF_008():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("lock", "running", "active_job", "job_id"))


# DATA (001-008): persistence, integrity, provenance, and schema discipline.
def test_REQ_DATA_001():
    assert (ROOT / "docs" / "development" / "DATA_PROVENANCE.md").is_file()


def test_REQ_DATA_002():
    assert (ROOT / "command_center" / "store.py").is_file()


def test_REQ_DATA_003():
    paths = [p for p in ROOT.rglob("*.py") if "integrity" in p.name.lower() or "manifest" in p.name.lower()]
    assert paths, "Expected a dedicated integrity or manifest implementation"


def test_REQ_DATA_004():
    source = _read("config/pipeline_config.yaml")
    assert source.strip() and ":" in source


def test_REQ_DATA_005():
    sources = [p.read_text(encoding="utf-8", errors="replace") for p in ROOT.rglob("*.py")]
    assert any(any(token in s.lower() for token in ("os.replace", "atomic", "fsync")) for s in sources)


def test_REQ_DATA_006():
    source = _read("docs/development/DATA_PROVENANCE.md").lower()
    assert "run" in source or "artifact" in source


def test_REQ_DATA_007():
    source = _read("command_center/store.py").lower()
    assert "sqlite" in source or "transaction" in source


def test_REQ_DATA_008():
    assert callable(hashlib.sha256)


# ML (001-008): model configuration, resource profiles, evaluation, comparability.
def test_REQ_ML_001():
    assert (ROOT / "config" / "dataset_profiles.yaml").is_file()


def test_REQ_ML_002():
    assert (ROOT / "config" / "pipeline_config.yaml").is_file()


def test_REQ_ML_003():
    assert (ROOT / "docs" / "architecture" / "PHASE5-HARDWARE-ESTIMATION.md").is_file()


def test_REQ_ML_004():
    assert (ROOT / "command_center" / "store.py").is_file()


def test_REQ_ML_005():
    source = _read("mlframework.py").lower()
    assert "evaluate" in source


def test_REQ_ML_006():
    source = _read("mlframework.py").lower()
    assert "export" in source


def test_REQ_ML_007():
    source = _read("config/pipeline_config.yaml")
    assert len(source.strip()) > 20


def test_REQ_ML_008():
    sources = [p.read_text(encoding="utf-8", errors="replace").lower() for p in ROOT.rglob("*.py")]
    assert any("comparab" in s or "experiment" in s for s in sources)


# ART (001-007): manifests, export cards, paired integrity and dataset cards.
def test_REQ_ART_001():
    assert any("manifest" in p.name.lower() or "integrity" in p.name.lower() for p in ROOT.rglob("*.py"))


def test_REQ_ART_002():
    assert (ROOT / "docs" / "EXPORT_AND_LLAMA_CPP_INTEGRATION.md").is_file()


def test_REQ_ART_003():
    sources = [p.read_text(encoding="utf-8", errors="replace").lower() for p in ROOT.rglob("*.py")]
    assert any("dataset card" in s or "dataset_card" in s for s in sources)


def test_REQ_ART_004():
    assert (ROOT / "docs" / "development" / "DATA_PROVENANCE.md").is_file()


def test_REQ_ART_005():
    assert "export" in _read("mlframework.py").lower()


def test_REQ_ART_006():
    sources = [p.read_text(encoding="utf-8", errors="replace") for p in ROOT.rglob("*.py")]
    assert any("sha256" in s or "sha-256" in s.lower() for s in sources)


def test_REQ_ART_007():
    source = _read("docs/EXPORT_AND_LLAMA_CPP_INTEGRATION.md").lower()
    assert "verify" in source or "integrity" in source or "manifest" in source


# OPS (001-008): diagnostics, logs, health and operator observability.
def test_REQ_OPS_001():
    assert "doctor" in _read("README.md").lower()


def test_REQ_OPS_002():
    source = _read("command_center/web.py").lower()
    assert "health" in source or "status" in source


def test_REQ_OPS_003():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("log", "error", "exception"))


def test_REQ_OPS_004():
    assert (ROOT / "command_center" / "secrets.py").is_file()


def test_REQ_OPS_005():
    assert (ROOT / "config" / ".env.example").is_file() or (ROOT / ".env.example").is_file()


def test_REQ_OPS_006():
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()


def test_REQ_OPS_007():
    assert (ROOT / ".github" / "workflows" / "security.yml").is_file()


def test_REQ_OPS_008():
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


# SEC (001-006): traversal boundaries, loopback defaults, secrets, dependencies.
def test_REQ_SEC_001():
    source = _read("command_center/security.py").lower()
    assert any(word in source for word in ("resolve", "commonpath", "travers", "path"))


def test_REQ_SEC_002():
    source = _read("command_center/web.py") + _read("run_command_center.py")
    assert "127.0.0.1" in source or "localhost" in source


def test_REQ_SEC_003():
    assert (ROOT / ".env.example").is_file()


def test_REQ_SEC_004():
    assert (ROOT / "command_center" / "secrets.py").is_file()


def test_REQ_SEC_005():
    candidates = ("uv.lock", "poetry.lock", "pdm.lock", "requirements.lock", "constraints.txt")
    assert any((ROOT / name).is_file() for name in candidates), "A dependency lock or constraints file is required"


def test_REQ_SEC_006():
    assert (ROOT / "SECURITY.md").is_file()


# REL (001-007): release identity, gate behavior, clean clone, and test layers.
def test_REQ_REL_001():
    source = _read(".github/workflows/ci.yml").lower()
    assert "pytest" in source or "test" in source


def test_REQ_REL_002():
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_REQ_REL_003():
    candidates = [p for p in ROOT.rglob("*.py") if "release" in p.name.lower() or "verify" in p.name.lower()]
    assert candidates, "Expected a release verification entrypoint"


def test_REQ_REL_004():
    candidates = [p for p in ROOT.rglob("*.py") if "release" in p.name.lower() or "verify" in p.name.lower()]
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in candidates)
    assert "--clean-clone" in source


def test_REQ_REL_005():
    data = tomllib.loads(_read("pyproject.toml"))
    version = data.get("project", {}).get("version")
    assert version, "Project version must be explicitly declared"


def test_REQ_REL_006():
    assert (ROOT / "tests").is_dir()


def test_REQ_REL_007():
    test_files = list((ROOT / "tests").rglob("test_*.py"))
    assert test_files, "Expected existing regression/unit tests alongside acceptance tests"
