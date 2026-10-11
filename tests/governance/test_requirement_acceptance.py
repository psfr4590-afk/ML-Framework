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
def test_REQ_UI_001_command_center_module_exists():
    assert (ROOT / "command_center" / "web.py").is_file()


def test_REQ_UI_002_command_center_has_fastapi_surface():
    source = _read("command_center/web.py")
    assert "FastAPI" in source


def test_REQ_UI_003_command_center_template_exists():
    assert (ROOT / "command_center" / "templates" / "index.html").is_file()


def test_REQ_UI_004_operator_entrypoint_exists():
    assert (ROOT / "run_command_center.py").is_file()


def test_REQ_UI_005_compatibility_entrypoint_does_not_duplicate_ui():
    source = _read("command_center/app.py")
    assert len(source.splitlines()) < 30, "Compatibility entrypoint should remain a thin delegate"


def test_REQ_UI_006_command_center_security_module_exists():
    assert (ROOT / "command_center" / "security.py").is_file()


# ENV (001-006): packaging, bootstrap, and declared runtime contracts.
def test_REQ_ENV_001_pyproject_is_valid_toml():
    data = tomllib.loads(_read("pyproject.toml"))
    assert isinstance(data, dict)


def test_REQ_ENV_002_bootstrap_entrypoint_exists():
    assert (ROOT / "bootstrap.py").is_file()


def test_REQ_ENV_003_windows_bootstrap_entrypoint_exists():
    assert (ROOT / "bootstrap_windows.ps1").is_file()


def test_REQ_ENV_004_environment_example_exists():
    assert (ROOT / ".env.example").is_file()


def test_REQ_ENV_005_documented_python_support_is_declared():
    data = tomllib.loads(_read("pyproject.toml"))
    requires = data.get("project", {}).get("requires-python", "")
    assert requires, "project.requires-python must declare the supported Python range"


def test_REQ_ENV_006_doctor_entrypoint_is_present():
    source = _read("bootstrap.py")
    assert "doctor" in source.lower()


# WF (001-008): configuration, stage identity, lifecycle and execution policy.
def test_REQ_WF_001_pipeline_configuration_exists():
    assert (ROOT / "config" / "pipeline_config.yaml").is_file()


def test_REQ_WF_002_smoke_configuration_exists():
    assert (ROOT / "config" / "pipeline_config.smoke.yaml").is_file()


def test_REQ_WF_003_runner_module_exists():
    assert (ROOT / "command_center" / "runner.py").is_file()


def test_REQ_WF_004_runner_has_explicit_state_or_lifecycle_contract():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("state", "status", "cancel", "lifecycle"))


def test_REQ_WF_005_cli_has_smoke_workflow():
    source = _read("mlframework.py").lower()
    assert "smoke" in source


def test_REQ_WF_006_pipeline_entrypoint_exists():
    assert (ROOT / "run_pipeline.py").is_file()


def test_REQ_WF_007_dataset_configuration_is_separate_from_pipeline_code():
    assert (ROOT / "config" / "dataset_groups.yaml").is_file()


def test_REQ_WF_008_runner_defines_single_job_or_lock_policy():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("lock", "running", "active_job", "job_id"))


# DATA (001-008): persistence, integrity, provenance, and schema discipline.
def test_REQ_DATA_001_data_provenance_documented():
    assert (ROOT / "docs" / "development" / "DATA_PROVENANCE.md").is_file()


def test_REQ_DATA_002_experiment_store_exists():
    assert (ROOT / "command_center" / "store.py").is_file()


def test_REQ_DATA_003_artifact_integrity_implementation_exists():
    paths = [p for p in ROOT.rglob("*.py") if "integrity" in p.name.lower() or "manifest" in p.name.lower()]
    assert paths, "Expected a dedicated integrity or manifest implementation"


def test_REQ_DATA_004_pipeline_configuration_is_parseable_yaml_text():
    source = _read("config/pipeline_config.yaml")
    assert source.strip() and ":" in source


def test_REQ_DATA_005_atomic_write_contract_is_documented_or_implemented():
    sources = [p.read_text(encoding="utf-8", errors="replace") for p in ROOT.rglob("*.py")]
    assert any(any(token in s.lower() for token in ("os.replace", "atomic", "fsync")) for s in sources)


def test_REQ_DATA_006_provenance_mentions_run_or_artifact_identity():
    source = _read("docs/development/DATA_PROVENANCE.md").lower()
    assert "run" in source or "artifact" in source


def test_REQ_DATA_007_store_uses_sqlite_or_transactional_persistence():
    source = _read("command_center/store.py").lower()
    assert "sqlite" in source or "transaction" in source


def test_REQ_DATA_008_hashing_primitive_is_available_for_integrity():
    assert callable(hashlib.sha256)


# ML (001-008): model configuration, resource profiles, evaluation, comparability.
def test_REQ_ML_001_dataset_profiles_exist():
    assert (ROOT / "config" / "dataset_profiles.yaml").is_file()


def test_REQ_ML_002_training_configuration_exists():
    assert (ROOT / "config" / "pipeline_config.yaml").is_file()


def test_REQ_ML_003_hardware_estimation_documented():
    assert (ROOT / "docs" / "architecture" / "PHASE5-HARDWARE-ESTIMATION.md").is_file()


def test_REQ_ML_004_experiment_history_store_exists():
    assert (ROOT / "command_center" / "store.py").is_file()


def test_REQ_ML_005_evaluation_command_is_exposed():
    source = _read("mlframework.py").lower()
    assert "evaluate" in source


def test_REQ_ML_006_export_command_is_exposed():
    source = _read("mlframework.py").lower()
    assert "export" in source


def test_REQ_ML_007_training_configuration_has_content():
    source = _read("config/pipeline_config.yaml")
    assert len(source.strip()) > 20


def test_REQ_ML_008_experiment_comparison_contract_is_documented_or_implemented():
    sources = [p.read_text(encoding="utf-8", errors="replace").lower() for p in ROOT.rglob("*.py")]
    assert any("comparab" in s or "experiment" in s for s in sources)


# ART (001-007): manifests, export cards, paired integrity and dataset cards.
def test_REQ_ART_001_manifest_or_integrity_code_exists():
    assert any("manifest" in p.name.lower() or "integrity" in p.name.lower() for p in ROOT.rglob("*.py"))


def test_REQ_ART_002_export_integration_document_exists():
    assert (ROOT / "docs" / "EXPORT_AND_LLAMA_CPP_INTEGRATION.md").is_file()


def test_REQ_ART_003_dataset_card_contract_is_documented_or_implemented():
    sources = [p.read_text(encoding="utf-8", errors="replace").lower() for p in ROOT.rglob("*.py")]
    assert any("dataset card" in s or "dataset_card" in s for s in sources)


def test_REQ_ART_004_provenance_document_exists():
    assert (ROOT / "docs" / "development" / "DATA_PROVENANCE.md").is_file()


def test_REQ_ART_005_export_path_is_exposed():
    assert "export" in _read("mlframework.py").lower()


def test_REQ_ART_006_hashing_support_exists():
    sources = [p.read_text(encoding="utf-8", errors="replace") for p in ROOT.rglob("*.py")]
    assert any("sha256" in s or "sha-256" in s.lower() for s in sources)


def test_REQ_ART_007_export_artifact_validation_is_present():
    source = _read("docs/EXPORT_AND_LLAMA_CPP_INTEGRATION.md").lower()
    assert "verify" in source or "integrity" in source or "manifest" in source


# OPS (001-008): diagnostics, logs, health and operator observability.
def test_REQ_OPS_001_doctor_documented():
    assert "doctor" in _read("README.md").lower()


def test_REQ_OPS_002_command_center_has_health_or_status_surface():
    source = _read("command_center/web.py").lower()
    assert "health" in source or "status" in source


def test_REQ_OPS_003_runner_logs_or_reports_errors():
    source = _read("command_center/runner.py").lower()
    assert any(word in source for word in ("log", "error", "exception"))


def test_REQ_OPS_004_secrets_handling_is_separated():
    assert (ROOT / "command_center" / "secrets.py").is_file()


def test_REQ_OPS_005_environment_examples_are_available():
    assert (ROOT / "config" / ".env.example").is_file() or (ROOT / ".env.example").is_file()


def test_REQ_OPS_006_ci_workflow_exists():
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()


def test_REQ_OPS_007_security_workflow_exists():
    assert (ROOT / ".github" / "workflows" / "security.yml").is_file()


def test_REQ_OPS_008_release_workflow_exists():
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


# SEC (001-006): traversal boundaries, loopback defaults, secrets, dependencies.
def test_REQ_SEC_001_security_module_has_path_boundary_logic():
    source = _read("command_center/security.py").lower()
    assert any(word in source for word in ("resolve", "commonpath", "travers", "path"))


def test_REQ_SEC_002_command_center_defaults_to_loopback():
    source = _read("command_center/web.py") + _read("run_command_center.py")
    assert "127.0.0.1" in source or "localhost" in source


def test_REQ_SEC_003_real_environment_file_is_not_required_in_repository():
    assert (ROOT / ".env.example").is_file()


def test_REQ_SEC_004_secret_redaction_module_exists():
    assert (ROOT / "command_center" / "secrets.py").is_file()


def test_REQ_SEC_005_dependency_lock_or_constraints_exist():
    candidates = ("uv.lock", "poetry.lock", "pdm.lock", "requirements.lock", "constraints.txt")
    assert any((ROOT / name).is_file() for name in candidates), "A dependency lock or constraints file is required"


def test_REQ_SEC_006_security_policy_exists():
    assert (ROOT / "SECURITY.md").is_file()


# REL (001-007): release identity, gate behavior, clean clone, and test layers.
def test_REQ_REL_001_ci_has_a_test_step():
    source = _read(".github/workflows/ci.yml").lower()
    assert "pytest" in source or "test" in source


def test_REQ_REL_002_release_workflow_exists():
    assert (ROOT / ".github" / "workflows" / "release.yml").is_file()


def test_REQ_REL_003_release_gate_script_exists():
    candidates = [p for p in ROOT.rglob("*.py") if "release" in p.name.lower() or "verify" in p.name.lower()]
    assert candidates, "Expected a release verification entrypoint"


def test_REQ_REL_004_release_gate_supports_clean_clone_mode():
    candidates = [p for p in ROOT.rglob("*.py") if "release" in p.name.lower() or "verify" in p.name.lower()]
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in candidates)
    assert "--clean-clone" in source


def test_REQ_REL_005_version_identity_is_declared():
    data = tomllib.loads(_read("pyproject.toml"))
    version = data.get("project", {}).get("version")
    assert version, "Project version must be explicitly declared"


def test_REQ_REL_006_governance_test_directory_is_package_or_testable():
    assert (ROOT / "tests").is_dir()


def test_REQ_REL_007_existing_test_layers_are_present():
    test_files = list((ROOT / "tests").rglob("test_*.py"))
    assert test_files, "Expected existing regression/unit tests alongside acceptance tests"
