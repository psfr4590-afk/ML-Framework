from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("model_lab_bootstrap", ROOT / "bootstrap.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_resolves_root_from_script_location():
    bootstrap = _load_bootstrap()
    assert bootstrap.project_root() == ROOT
    assert bootstrap.RECONCILER == ROOT / "scripts" / "reconcile_environment.py"


def test_bootstrap_llamacpp_passes_project_root(monkeypatch):
    bootstrap = _load_bootstrap()
    calls = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    assert bootstrap.ensure_llamacpp() == 0

    command, kwargs = calls[0]
    assert command[:3] == [bootstrap.sys.executable, str(bootstrap.RECONCILER), "--project-root"]
    assert command[3] == str(ROOT)
    assert command[4:] == ["--ensure-llamacpp"]
    assert kwargs["cwd"] == ROOT
    assert kwargs["check"] is False
