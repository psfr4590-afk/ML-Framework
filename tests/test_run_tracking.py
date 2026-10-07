from __future__ import annotations

import json
from pathlib import Path

from pipeline.run_tracking import RunTracker


def _patch_host(monkeypatch) -> None:
    monkeypatch.setattr("pipeline.run_tracking._git_state", lambda root: {
        "commit": "abc123", "branch": "phase3", "dirty": False, "status_entries": []
    })
    monkeypatch.setattr("pipeline.run_tracking._hardware", lambda: {"cpu": "test"})
    monkeypatch.setattr("pipeline.run_tracking._torch_environment", lambda: {"cuda_available": False})


def test_run_manifest_has_single_authoritative_identity(tmp_path: Path, monkeypatch) -> None:
    _patch_host(monkeypatch)
    tracker = RunTracker(
        tmp_path, tmp_path / "output", run_id="run_test_001",
        dataset_id="dataset_001", experiment_id="exp_test_001",
        configuration={"train": {"total_steps": 10}},
        dataset_identity={"catalog_sha256": "abc"},
        source_identity={"sources": [{"kind": "web"}]},
    )
    data = json.loads(tracker.path.read_text(encoding="utf-8"))
    assert tracker.path == tmp_path / "output" / "runs" / "run_test_001" / "run_manifest.json"
    assert data["run_id"] == "run_test_001"
    assert data["dataset_id"] == "dataset_001"
    assert data["experiment_id"] == "exp_test_001"
    assert data["git"]["commit"] == "abc123"
    assert data["final_status"] == "RUNNING"


def test_stage_record_captures_lifecycle_inputs_outputs_and_hashes(tmp_path: Path, monkeypatch) -> None:
    _patch_host(monkeypatch)
    source = tmp_path / "input.txt"
    output = tmp_path / "output.txt"
    source.write_text("input", encoding="utf-8")
    output.write_text("output", encoding="utf-8")
    tracker = RunTracker(tmp_path, tmp_path / "output", run_id="run_stage", dataset_id="ds", experiment_id="exp", configuration={})
    tracker.start_stage("clean", inputs=[source])
    tracker.finish_stage("clean", outputs=[output], warnings=["test warning"], metrics={"rows": 1})
    data = json.loads(tracker.path.read_text(encoding="utf-8"))
    stage = data["stages"]["clean"]
    assert stage["status"] == "PASS"
    assert stage["end"]
    assert stage["duration_seconds"] >= 0
    assert stage["inputs"][0]["sha256"]
    assert stage["outputs"][0]["sha256"]
    assert stage["artifact_hashes"]["output.txt"] == stage["outputs"][0]["sha256"]
    assert data["warnings"] == ["test warning"]
    assert data["metrics"]["clean"]["rows"] == 1


def test_failed_stage_and_run_are_durable(tmp_path: Path, monkeypatch) -> None:
    _patch_host(monkeypatch)
    tracker = RunTracker(tmp_path, tmp_path / "output", run_id="run_fail", dataset_id="ds", experiment_id="exp", configuration={})
    tracker.start_stage("train")
    tracker.fail_stage("train", RuntimeError("boom"))
    tracker.finish_run("FAILED")
    data = json.loads(tracker.path.read_text(encoding="utf-8"))
    assert data["stages"]["train"]["status"] == "FAILED"
    assert data["errors"] == ["RuntimeError: boom"]
    assert data["final_status"] == "FAILED"


def test_resume_reuses_same_run_manifest(tmp_path: Path, monkeypatch) -> None:
    _patch_host(monkeypatch)
    tracker = RunTracker(tmp_path, tmp_path / "output", run_id="run_resume", dataset_id="ds", experiment_id="exp", configuration={})
    tracker.start_stage("train")
    tracker.finish_stage("train")
    resumed = RunTracker.resume(tmp_path, tmp_path / "output", tracker.path)
    assert resumed.run_id == tracker.run_id
    assert resumed.manifest["final_status"] == "RUNNING"


def test_finish_run_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    _patch_host(monkeypatch)
    tracker = RunTracker(tmp_path, tmp_path / "output", run_id="run_once", dataset_id="ds", experiment_id="exp", configuration={})
    tracker.finish_run("PASS")
    first = json.loads(tracker.path.read_text(encoding="utf-8"))
    ended = first["timestamps"]["ended"]
    tracker.finish_run("FAILED")
    second = json.loads(tracker.path.read_text(encoding="utf-8"))
    assert second["final_status"] == "PASS"
    assert second["timestamps"]["ended"] == ended
