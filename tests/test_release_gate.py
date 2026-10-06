from __future__ import annotations

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
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "model-lab-framework.whl").write_bytes(b"package")


def test_rc_report_is_single_machine_readable_gate(tmp_path, monkeypatch):
    _seed_report_environment(tmp_path, monkeypatch)
    verify_release.NATIVE_EVIDENCE.clear()
    verify_release.NATIVE_EVIDENCE.update({
        "provenance": True, "lineage": True, "dataset": True, "source_retrieval": True,
        "checkpoint": True, "best_checkpoint": True, "reproducibility": True,
        "hardware": True, "auto_sizing": True, "eta": True, "evaluation": True,
        "sqlite": True, "export": True, "inference": True,
        "ui_backend_connectivity": True, "clean_clone": True, "secrets": True,
    })

    assert verify_release._write_release_report(static_failures=[], native_requested=True, native_rc=0) == 0
    report = json.loads((tmp_path / "release-evidence" / "release_report.json").read_text(encoding="utf-8"))
    assert report["release"] == "ML-FRAMEWORK RC"
    assert report["status"] == "PASS"
    assert {item["name"] for item in report["checks"]} >= {
        "tests", "configs", "provenance", "lineage", "dataset", "source_retrieval",
        "checkpoint", "best_checkpoint", "reproducibility", "hardware", "auto_sizing",
        "eta", "evaluation", "sqlite", "ui_backend_connectivity", "export", "inference",
        "clean_clone", "documentation", "secrets", "git_state", "release_artifacts",
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
