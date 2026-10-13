from __future__ import annotations

from types import SimpleNamespace

from command_center import runner


def test_dead_pid_is_not_the_same_process(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: False)

    assert not runner._same_process_identity({"pid": 1234, "process_identity": {"pid": 1234, "create_time": 10.0}})


def test_matching_process_creation_time_preserves_worker_identity(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(
        runner,
        "psutil",
        SimpleNamespace(Process=lambda pid: SimpleNamespace(create_time=lambda: 10.0)),
    )

    assert runner._same_process_identity({"pid": 1234, "process_identity": {"pid": 1234, "create_time": 10.0}})


def test_reused_pid_with_different_creation_time_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(
        runner,
        "psutil",
        SimpleNamespace(Process=lambda pid: SimpleNamespace(create_time=lambda: 20.0)),
    )

    assert not runner._same_process_identity({"pid": 1234, "process_identity": {"pid": 1234, "create_time": 10.0}})


def test_missing_identity_evidence_preserves_live_pid(monkeypatch) -> None:
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(runner, "psutil", None)

    assert runner._same_process_identity({"pid": 1234, "process_identity": None})
    assert runner._same_process_identity({"pid": 1234})
