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


def _assert_pip_network_options(command, bootstrap):
    options = list(bootstrap.PIP_NETWORK_OPTIONS)
    assert command[4 : 4 + len(options)] == options


def _assert_requirements_argument(command, requirements, bootstrap):
    _assert_pip_network_options(command, bootstrap)
    install_args = command[4:]
    assert "-r" in install_args
    assert install_args[install_args.index("-r") + 1] == str(requirements)


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


def test_bootstrap_install_defaults_to_cpu_torch(monkeypatch):
    bootstrap = _load_bootstrap()
    calls = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    assert bootstrap.install() == 0

    assert len(calls) == 2
    core_command, core_kwargs = calls[0]
    torch_command, torch_kwargs = calls[1]
    _assert_requirements_argument(core_command, bootstrap.REQUIREMENTS, bootstrap)
    _assert_requirements_argument(torch_command, bootstrap.TORCH_REQUIREMENTS, bootstrap)
    assert torch_command[-2:] == ["--index-url", bootstrap.CPU_TORCH_INDEX]
    assert core_kwargs["cwd"] == ROOT
    assert torch_kwargs["cwd"] == ROOT


def test_bootstrap_can_use_default_torch_index(monkeypatch):
    bootstrap = _load_bootstrap()
    calls = []

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    assert bootstrap.install("default") == 0

    assert len(calls) == 2
    torch_command, _ = calls[1]
    _assert_requirements_argument(torch_command, bootstrap.TORCH_REQUIREMENTS, bootstrap)
    assert "--index-url" not in torch_command
