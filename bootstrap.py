#!/usr/bin/env python3
"""Canonical Model Lab bootstrapper.

Resolves the project from this file, validates the environment, and optionally
installs the declared core dependencies. It never depends on the caller's cwd.
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
MIN_PYTHON = (3, 11)
REQUIRED = ("yaml", "requests", "bs4", "lxml", "numpy", "tokenizers", "torch")


def project_root() -> Path:
    return ROOT


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def doctor() -> int:
    failures: list[str] = []
    print(f"Project root: {ROOT}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    if sys.version_info < MIN_PYTHON:
        failures.append("Python 3.11+ required")
    for name in REQUIRED:
        state = "OK" if _importable(name) else "MISSING"
        print(f"{name}: {state}")
        if state != "OK":
            failures.append(name)
    for exe in ("git", "cmake"):
        print(f"{exe}: {'OK' if shutil.which(exe) else 'MISSING'}")
    print("Bootstrap doctor: PASS" if not failures else "Bootstrap doctor: FAIL")
    return 0 if not failures else 2


def install() -> int:
    req = ROOT / "requirements.txt"
    if not req.is_file():
        print(f"Missing requirements file: {req}", file=sys.stderr)
        return 2
    command = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    print("$", " ".join(command))
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Model Lab bootstrap")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        return install()
    return doctor()


if __name__ == "__main__":
    raise SystemExit(main())
