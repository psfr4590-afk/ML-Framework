#!/usr/bin/env python3
"""Generate reproducibility evidence for a release environment."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release-evidence"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT, check=True, capture_output=True, text=True)
    (OUT / "pip-freeze.txt").write_text(freeze.stdout, encoding="utf-8")
    run("cyclonedx-py", "requirements", "-i", "requirements.txt", "-o", str(OUT / "sbom.json"), "--format", "json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
