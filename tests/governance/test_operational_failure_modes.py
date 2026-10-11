"""Supplemental operational failure-mode tests for governance hardening.

These tests complement the 64 catalog-mapped targets without changing their
traceability identities. All filesystem effects are isolated in tmp_path.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_runner_stop_terminates_active_worker(monkeypatch):
    from command_center import runner

    class Process:
        terminated = False
        def poll(self):
            return None
        def terminate(self):
            self.terminated = True

    process = Process()
    with runner.LOCK:
        runner.RUNS[991101] = process
    try:
        assert runner.stop(991101) is True
        assert process.terminated is True
    finally:
        with runner.LOCK:
            runner.RUNS.pop(991101, None)


def test_runner_stop_does_not_claim_to_cancel_starting_worker():
    from command_center import runner

    with runner.LOCK:
        runner.RUNS[991102] = runner._STARTING
    try:
        assert runner.stop(991102) is False
    finally:
        with runner.LOCK:
            runner.RUNS.pop(991102, None)


def test_orphan_recovery_marks_dead_worker_failed(monkeypatch, tmp_path):
    from command_center import runner

    dataset = {"id": 991103, "status": "RUNNING", "stages": {"train": "running"}}
    state_path = tmp_path / "runner_state.json"
    state_path.write_text(json.dumps({"pid": 991104, "stage": "train"}), encoding="utf-8")
    events = []
    updates = []
    monkeypatch.setattr(runner.store, "list", lambda: [dataset])
    monkeypatch.setattr(runner, "_state_path", lambda did: state_path)
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(runner.store, "update", lambda did, **fields: updates.append((did, fields)))
    monkeypatch.setattr(runner.store, "event", lambda *args: events.append(args))
    monkeypatch.setattr(runner, "_clear_state", lambda did: state_path.unlink(missing_ok=True))

    runner.reconcile_orphaned_runs()

    assert updates[0][1]["status"] == "ERROR"
    assert updates[0][1]["stages"]["train"] == "failed"
    assert events[0][1] == "stage.recovered_orphan"


def test_orphan_recovery_preserves_live_worker(monkeypatch, tmp_path):
    from command_center import runner

    dataset = {"id": 991105, "status": "RUNNING", "stages": {"train": "running"}}
    state_path = tmp_path / "runner_state.json"
    state_path.write_text(json.dumps({"pid": 991106, "stage": "train"}), encoding="utf-8")
    updates = []
    monkeypatch.setattr(runner.store, "list", lambda: [dataset])
    monkeypatch.setattr(runner, "_state_path", lambda did: state_path)
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(runner.store, "update", lambda *args, **kwargs: updates.append(args))
    monkeypatch.setattr(runner.store, "event", lambda *args: pytest.fail("live worker must not be recovered as orphan"))

    runner.reconcile_orphaned_runs()
    assert updates == []
    assert state_path.exists()


def test_artifact_provenance_mismatch_and_manifest_corruption_fail_closed(tmp_path):
    from pipeline.integrity import write_manifest, artifact_valid, manifest_path

    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"valid artifact bytes")
    write_manifest(artifact, kind="model", provenance={"run_id": "run-a", "config": "cfg-a"})
    assert artifact_valid(artifact, expected_provenance={"run_id": "run-a", "config": "cfg-a"})
    assert not artifact_valid(artifact, expected_provenance={"run_id": "run-b", "config": "cfg-a"})
    manifest_path(artifact).write_text("{invalid", encoding="utf-8")
    assert not artifact_valid(artifact)


def test_source_manifest_rejects_dataset_group_mismatch(tmp_path):
    from scripts.verify_release import _validate_source_manifest

    path = tmp_path / "source_manifest.json"
    path.write_text(json.dumps({
        "schema": 2, "run_id": "fixture", "dataset_group": "group-a",
        "retrieval_started_at": "2026-01-01T00:00:00+00:00",
        "retrieval_completed_at": "2026-01-01T00:00:01+00:00",
        "source_definition_sha256": "0" * 64,
        "source_definition_files": {},
        "sources": [{"kind": "local_fixture", "identifier": "x", "revision": "1",
                     "license": "test", "raw_source_sha256": None,
                     "dataset_group": "group-b"}],
        "rights_note": "test fixture"
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="dataset-group identity"):
        _validate_source_manifest(path)


def test_release_gate_rejects_rc_without_required_flags(monkeypatch):
    from scripts import verify_release

    monkeypatch.setattr("sys.argv", ["verify_release.py", "--profile", "rc"])
    with pytest.raises(SystemExit) as exc:
        verify_release.main()
    assert exc.value.code == 2


def test_release_gate_rejects_skip_tests(monkeypatch):
    from scripts import verify_release

    monkeypatch.setattr("sys.argv", ["verify_release.py", "--skip-tests"])
    with pytest.raises(SystemExit) as exc:
        verify_release.main()
    assert exc.value.code == 2


def test_project_version_matches_declared_package_version():
    import tomllib
    from scripts.verify_release import _project_version, ROOT

    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert _project_version() == declared


def test_worker_log_redacts_injected_credential_value(monkeypatch, tmp_path):
    from command_center import runner

    secret = "fixture-secret-value-123"
    log_path = tmp_path / "logs" / "command-center.log"
    class FakeProcess:
        pid = 123456
        stdout = iter([f"starting worker with token={secret}\\n"])
        def wait(self):
            return 1

    dataset = {"id": 991107, "stages": {}, "status": "NEW"}
    monkeypatch.setattr(runner.store, "get", lambda did: dict(dataset))
    def update(did, **fields):
        dataset.update(fields)
    monkeypatch.setattr(runner.store, "update", update)
    monkeypatch.setattr(runner.store, "event", lambda *args: None)
    monkeypatch.setattr(runner.store, "path", lambda did: tmp_path)
    monkeypatch.setattr(runner, "_write_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_clear_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(runner, "credentials", type("Credentials", (), {
        "environment": staticmethod(lambda: {"HF_TOKEN": secret})
    })())
    monkeypatch.setattr(runner.store, "refresh_stats", lambda did: None)
    monkeypatch.setattr(runner.store, "refresh_pipeline_state", lambda did: None)

    runner._run(991107, "clean")
    output = log_path.read_text(encoding="utf-8")
    assert "[REDACTED]" in output
    assert secret not in output
