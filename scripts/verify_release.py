#!/usr/bin/env python3
"""Deterministic production release gate for Model Lab."""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=ROOT, text=True, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Model Lab production release gate.")
    parser.add_argument("--bootstrap-native", action="store_true")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="not allowed for a release gate; retained only to produce a clear error",
    )
    args = parser.parse_args()

    if args.skip_tests:
        print("RELEASE GATE FAILED: --skip-tests is not allowed for a production verification.")
        return 2

    failures: list[str] = []
    compile_targets = ["pipeline", "command_center", "scripts", "run_pipeline.py", "run_command_center.py", "launch.py"]
    if run([sys.executable, "-m", "compileall", "-q", *compile_targets]):
        failures.append("compileall")
    if run([sys.executable, "-m", "pytest", "-q"]):
        failures.append("pytest")
    native_checked = False
    if args.bootstrap_native:
        native_checked = True
        script = ROOT / "scripts" / "reconcile_environment.py"
        if run([sys.executable, str(script), "--project-root", str(ROOT), "--ensure-llamacpp"]):
            failures.append("llama.cpp-bootstrap")
    if run([sys.executable, "run_pipeline.py", "--doctor"]):
        failures.append("doctor-required")

    if failures:
        print("RELEASE GATE FAILED:", ", ".join(failures))
        print("Platform:", platform.platform())
        return 2

    if native_checked:
        print("RELEASE GATE PASSED: syntax, tests, environment, and native export prerequisites are green.")
    else:
        print("RELEASE GATE PASSED: syntax, tests, and required environment checks are green.")
        print("Native export prerequisites were not checked; use --bootstrap-native for that gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
