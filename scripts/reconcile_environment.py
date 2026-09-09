#!/usr/bin/env python3
"""Reconcile native build prerequisites without duplicating project logic."""
from __future__ import annotations
import argparse, platform, subprocess, sys
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--ensure-llamacpp", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    if not args.ensure_llamacpp:
        return 0
    script = root / "scripts" / ("bootstrap_llama_cpp.ps1" if platform.system() == "Windows" else "bootstrap_llama_cpp.sh")
    if not script.is_file():
        print(f"Missing native bootstrap script: {script}", file=sys.stderr)
        return 2
    command = (["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)] if platform.system() == "Windows" else ["bash", str(script)])
    print("Reconciling native llama.cpp toolchain...")
    return subprocess.run(command, cwd=root, check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main())
