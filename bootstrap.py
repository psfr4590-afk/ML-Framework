#!/usr/bin/env python3
"""Canonical Model Lab bootstrapper.

Resolves the project from this file, validates the environment, and optionally
installs the declared dependencies or reconciles the local llama.cpp toolchain.
It never depends on the caller's cwd.
"""
from __future__ import annotations

import argparse
import importlib
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECONCILER = ROOT / "scripts" / "reconcile_environment.py"
REQUIREMENTS = ROOT / "requirements.txt"
TORCH_REQUIREMENTS = ROOT / "requirements-torch.txt"
MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 14)
REQUIRED = ("yaml", "requests", "bs4", "lxml", "numpy", "tokenizers", "torch")
CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
PIP_NETWORK_OPTIONS = ("--timeout", "120", "--retries", "5")


def project_root() -> Path:
    return ROOT


def _python_supported() -> bool:
    version = sys.version_info[:2]
    return MIN_PYTHON <= version < MAX_PYTHON_EXCLUSIVE


def _python_requirement_message() -> str:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return f"Python 3.11-3.13 required; found Python {version}. Python 3.14+ is not supported because the pinned dependency set includes lxml 5.x without a compatible Windows CPython 3.14 wheel."


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def doctor() -> int:
    failures: list[str] = []
    print(f"Project root: {ROOT}")
    print(f"Reconciler: {'OK' if RECONCILER.is_file() else 'MISSING'} ({RECONCILER})")
    if not RECONCILER.is_file():
        failures.append("scripts/reconcile_environment.py missing")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    if not _python_supported():
        failures.append(_python_requirement_message())
    for name in REQUIRED:
        state = "OK" if _importable(name) else "MISSING"
        print(f"{name}: {state}")
        if state != "OK":
            failures.append(name)
    for exe in ("git", "cmake"):
        print(f"{exe}: {'OK' if shutil.which(exe) else 'MISSING'}")
    print("Bootstrap doctor: PASS" if not failures else "Bootstrap doctor: FAIL")
    return 0 if not failures else 2


def _pip_install(requirements: Path, *extra: str) -> int:
    if not requirements.is_file():
        print(f"Missing requirements file: {requirements}", file=sys.stderr)
        return 2
    command = [sys.executable, "-m", "pip", "install", *PIP_NETWORK_OPTIONS, "-r", str(requirements), *extra]
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def install(torch_channel: str = "cpu") -> int:
    if not _python_supported():
        print(f"Bootstrap install aborted: {_python_requirement_message()}", file=sys.stderr)
        return 2
    result = _pip_install(REQUIREMENTS)
    if result != 0:
        return result
    if torch_channel == "cpu":
        return _pip_install(TORCH_REQUIREMENTS, "--index-url", CPU_TORCH_INDEX)
    return _pip_install(TORCH_REQUIREMENTS)


def ensure_llamacpp() -> int:
    if not RECONCILER.is_file():
        print(f"Missing reconciler: {RECONCILER}", file=sys.stderr)
        return 2
    command = [sys.executable, str(RECONCILER), "--project-root", str(ROOT), "--ensure-llamacpp"]
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Model Lab bootstrap")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--install", action="store_true")
    parser.add_argument(
        "--torch-channel",
        choices=("cpu", "default"),
        default="cpu",
        help="PyTorch wheel source for --install (default: cpu)",
    )
    parser.add_argument("--ensure-llamacpp", action="store_true")
    args = parser.parse_args()
    if args.ensure_llamacpp:
        return ensure_llamacpp()
    if args.install:
        return install(args.torch_channel)
    return doctor()


if __name__ == "__main__":
    raise SystemExit(main())
