from __future__ import annotations
import pytest

import json

from scripts import verify_release


def _seed_report_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    monkeypatch.setattr(
        verify_release,
        "_git_state",
        lambda _root: {"commit": "abc123", "branch": "main", "dirty": False, "status_entries": []},
    )
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "docs" / "development").mkdir(parents=True)
    (tmp_path / "docs" / "development" / "START_HERE.md").write_text("start", encoding="utf-8")


def test_rc_report_is_single_machine_readable_gate(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    verify_release.NATIVE_EVIDENCE.update({
        "provenance": True, "lineage": True, "dataset": True, "source_retrieval": True,
        "checkpoint": True, "best_checkpoint": True, "reproducibility": True,
        "hardware": True, "auto_sizing": True, "eta": True, "evaluation": True,
        "sqlite": True, "export": True, "inference": True,
        "ui_backend_connectivity": True, "clean_clone": True, "secrets": True,
        "package": True, "package_detail": "valid wheel fixture",
    })

    assert verify_release._write_release_report(static_failures=[], native_requested=True, native_rc=0) == 0
    report = json.loads((tmp_path / "release-evidence" / "release_report.json").read_text(encoding="utf-8"))
    assert report["release"] == "ML-FRAMEWORK RC"
    assert report["status"] == "PASS"
    assert {item["name"] for item in report["checks"]} >= {
        "tests", "configs", "provenance", "lineage", "dataset", "source_retrieval",
        "checkpoint", "best_checkpoint", "reproducibility", "hardware", "auto_sizing",
        "eta", "evaluation", "sqlite", "ui_backend_connectivity", "export", "inference",
        "clean_clone", "documentation", "secrets", "git_state", "package", "release_artifacts",
    }


def test_rc_report_fails_on_unknown_required_evidence(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    for name in (
        "provenance", "lineage", "dataset", "source_retrieval", "checkpoint",
        "best_checkpoint", "reproducibility", "hardware", "auto_sizing", "eta",
        "evaluation", "sqlite", "export", "inference", "secrets",
    ):
        verify_release.NATIVE_EVIDENCE[name] = True

    assert verify_release._write_release_report(static_failures=[], native_requested=True, native_rc=0) == 2
    report = json.loads((tmp_path / "release-evidence" / "release_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "FAIL"
    statuses = {item["name"]: item["status"] for item in report["checks"]}
    assert statuses["ui_backend_connectivity"] == "UNKNOWN"
    assert statuses["clean_clone"] == "UNKNOWN"
    assert statuses["package"] == "UNKNOWN"


def test_rc_report_fails_when_package_validation_fails(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    verify_release.NATIVE_EVIDENCE.update({
        "provenance": True, "lineage": True, "dataset": True, "source_retrieval": True,
        "checkpoint": True, "best_checkpoint": True, "reproducibility": True,
        "hardware": True, "auto_sizing": True, "eta": True, "evaluation": True,
        "sqlite": True, "export": True, "inference": True,
        "ui_backend_connectivity": True, "clean_clone": True, "secrets": True,
        "package": False, "package_detail": "wheel missing a required module",
    })
    assert verify_release._write_release_report(
        static_failures=[], native_requested=True, native_rc=0, profile="rc"
    ) == 2
    report = json.loads(
        (tmp_path / "release-evidence" / "release_report.json").read_text(encoding="utf-8")
    )
    statuses = {item["name"]: item["status"] for item in report["checks"]}
    assert report["status"] == "FAIL"
    assert statuses["package"] == "FAIL"



def test_rc_report_accepts_auto_sizing_evaluated_false(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    verify_release.NATIVE_EVIDENCE.update({
        "provenance": True, "lineage": True, "dataset": True,
        "source_retrieval": None, "checkpoint": True, "best_checkpoint": True,
        "reproducibility": True, "hardware": True, "auto_sizing": False,
        "eta": True, "evaluation": True, "sqlite": True, "export": True,
        "inference": True, "ui_backend_connectivity": True, "clean_clone": True,
        "secrets": True, "package": True, "package_detail": "valid wheel fixture",
    })

    assert verify_release._write_release_report(
        static_failures=[], native_requested=True, native_rc=0, profile="rc"
    ) == 0
    report = json.loads(
        (tmp_path / "release-evidence" / "release_report.json").read_text(encoding="utf-8")
    )
    statuses = {item["name"]: item["status"] for item in report["checks"]}
    assert statuses["auto_sizing"] == "PASS"
    assert statuses["source_retrieval"] == "UNKNOWN"
    assert "source_retrieval" not in report["required_checks"]


def test_rc_source_retrieval_required_only_when_executed(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    verify_release.NATIVE_EVIDENCE.update({
        "provenance": True, "lineage": True, "dataset": True,
        "source_retrieval": None, "checkpoint": True, "best_checkpoint": True,
        "reproducibility": True, "hardware": True, "auto_sizing": False,
        "eta": True, "evaluation": True, "sqlite": True, "export": True,
        "inference": True, "ui_backend_connectivity": True, "clean_clone": True,
        "secrets": True, "package": True, "package_detail": "valid wheel fixture",
    })

    assert verify_release._write_release_report(
        static_failures=[], native_requested=True, native_rc=0, profile="rc"
    ) == 0
    report_path = tmp_path / "release-evidence" / "release_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "source_retrieval" not in report["required_checks"]

    verify_release.NATIVE_EVIDENCE["source_retrieval"] = True
    assert verify_release._write_release_report(
        static_failures=[], native_requested=True, native_rc=0, profile="rc"
    ) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "source_retrieval" in report["required_checks"]
    statuses = {item["name"]: item["status"] for item in report["checks"]}
    assert statuses["source_retrieval"] == "PASS"


def _mock_wheel_build(tmp_path, monkeypatch, fault=None):
    import zipfile
    from pathlib import Path
    from types import SimpleNamespace

    monkeypatch.setattr(verify_release, "ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "model-lab-framework"\nversion = "1.3.0rc1"\n',
        encoding="utf-8",
    )

    def fake_run(command, cwd, capture_output, text, check):
        wheel_dir = Path(command[command.index("--wheel-dir") + 1])
        wheel_dir.mkdir(parents=True, exist_ok=True)
        wheel = wheel_dir / "model_lab_framework-1.3.0rc1-py3-none-any.whl"
        if fault == "corrupt":
            wheel.write_bytes(b"not a zip archive")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        version = "9.9.9" if fault == "wrong_version" else "1.3.0rc1"
        modules = [
            "run_pipeline.py", "mlframework.py", "run_command_center.py", "launch.py",
        ]
        if fault == "missing_module":
            modules.remove("launch.py")

        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                "model_lab_framework-1.3.0rc1.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: model-lab-framework\nVersion: {version}\n\n",
            )
            archive.writestr(
                "model_lab_framework-1.3.0rc1.dist-info/WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            archive.writestr("model_lab_framework-1.3.0rc1.dist-info/RECORD", "")
            archive.writestr(
                "model_lab_framework-1.3.0rc1.dist-info/entry_points.txt",
                "[console_scripts]\n"
                "mlab = run_pipeline:main\n"
                "mlframework = mlframework:main\n"
                "mlab-command-center = run_command_center:main\n"
                "mlab-launch = launch:main\n",
            )
            for module in modules:
                archive.writestr(module, "# test module\n")

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_release.subprocess, "run", fake_run)


def test_build_and_validate_wheel_accepts_valid_wheel(tmp_path, monkeypatch):
    _mock_wheel_build(tmp_path, monkeypatch)
    ok, detail = verify_release._build_and_validate_wheel()
    assert ok is True
    assert "Validated model_lab_framework-1.3.0rc1-py3-none-any.whl" in detail


def test_build_and_validate_wheel_rejects_missing_module(tmp_path, monkeypatch):
    _mock_wheel_build(tmp_path, monkeypatch, fault="missing_module")
    ok, detail = verify_release._build_and_validate_wheel()
    assert ok is False
    assert "Missing wheel modules" in detail


def test_build_and_validate_wheel_rejects_wrong_version(tmp_path, monkeypatch):
    _mock_wheel_build(tmp_path, monkeypatch, fault="wrong_version")
    ok, detail = verify_release._build_and_validate_wheel()
    assert ok is False
    assert "version does not match" in detail


def test_build_and_validate_wheel_rejects_corrupt_archive(tmp_path, monkeypatch):
    _mock_wheel_build(tmp_path, monkeypatch, fault="corrupt")
    ok, detail = verify_release._build_and_validate_wheel()
    assert ok is False
    assert "Wheel validation failed" in detail

def test_auto_sizing_evidence_reads_effective_training_configuration():
    evidence = verify_release._auto_sizing_evidence({
        "training_metadata": {
            "effective_configuration": {"auto_size": True},
        },
    })
    assert evidence is True


def test_auto_sizing_evidence_preserves_explicit_disabled_value():
    evidence = verify_release._auto_sizing_evidence({
        "training_metadata": {
            "effective_configuration": {"auto_size": False},
        },
    })
    assert evidence is False


def test_auto_sizing_evidence_supports_legacy_and_unknown_values():
    assert verify_release._auto_sizing_evidence({"auto_size": True}) is True
    assert verify_release._auto_sizing_evidence({"auto_size": False}) is False
    assert verify_release._auto_sizing_evidence({}) is None
    assert verify_release._auto_sizing_evidence(None) is None

def test_auto_sizing_evidence_reads_actual_run_manifest_shape():
    evidence = verify_release._auto_sizing_evidence({
        "effective_configuration": {"auto_size": False},
        "requested_configuration": {"auto_size": False},
    })
    assert evidence is False


def test_best_checkpoint_requires_real_best_manifest_contract():
    verify_release._validate_best_checkpoint_metadata({
        "checkpoint_kind": "best",
        "step": 12,
        "best_step": 12,
        "best_val_loss": 1.25,
    })


@pytest.mark.parametrize("metadata", [
    {"checkpoint_kind": "periodic", "step": 12, "best_step": 12, "best_val_loss": 1.25},
    {"checkpoint_kind": "best", "step": 12, "best_step": None, "best_val_loss": 1.25},
    {"checkpoint_kind": "best", "step": 12, "best_step": -1, "best_val_loss": 1.25},
    {"checkpoint_kind": "best", "step": 12, "best_step": 12, "best_val_loss": float("nan")},
    {"checkpoint_kind": "best", "step": 12, "best_step": 12, "best_val_loss": float("inf")},
    {"checkpoint_kind": "best", "step": True, "best_step": 12, "best_val_loss": 1.25},
])
def test_best_checkpoint_rejects_invalid_manifest(metadata):
    with pytest.raises(RuntimeError):
        verify_release._validate_best_checkpoint_metadata(metadata)


def _valid_identity_fixture():
    return {
        "dataset_config_sha256": "a" * 64,
        "tokenizer_config_sha256": "b" * 64,
        "shard_config_sha256": "c" * 64,
        "export_config_sha256": "d" * 64,
        "source_definition_sha256": "e" * 64,
    }


def test_checkpoint_identity_chain_requires_and_matches_all_stable_hashes():
    expected = _valid_identity_fixture()
    actual = dict(expected)
    # The legacy pipeline hash is deliberately not part of strict equality.
    expected["pipeline_config_sha256"] = "1" * 64
    actual["pipeline_config_sha256"] = "2" * 64
    verify_release._validate_checkpoint_identity_chain(expected, actual)


@pytest.mark.parametrize("missing_key", [
    "dataset_config_sha256",
    "tokenizer_config_sha256",
    "shard_config_sha256",
    "export_config_sha256",
    "source_definition_sha256",
])
def test_checkpoint_identity_chain_rejects_missing_hash(missing_key):
    expected = _valid_identity_fixture()
    actual = dict(expected)
    del actual[missing_key]
    with pytest.raises(RuntimeError, match=missing_key):
        verify_release._validate_checkpoint_identity_chain(expected, actual)


def test_checkpoint_identity_chain_rejects_mismatch_and_malformed_hash():
    expected = _valid_identity_fixture()
    actual = dict(expected)
    actual["shard_config_sha256"] = "f" * 64
    with pytest.raises(RuntimeError, match="identity mismatch"):
        verify_release._validate_checkpoint_identity_chain(expected, actual)

    actual = dict(expected)
    actual["export_config_sha256"] = "not-a-sha256"
    with pytest.raises(RuntimeError, match="export_config_sha256"):
        verify_release._validate_checkpoint_identity_chain(expected, actual)
