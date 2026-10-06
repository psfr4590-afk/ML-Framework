#!/usr/bin/env python3
"""Generate reproducibility evidence for a release environment."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release-evidence"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT, check=True, capture_output=True, text=True)
    (OUT / "pip-freeze.txt").write_text(freeze.stdout, encoding="utf-8")
    run("cyclonedx-py", "environment", "-o", str(OUT / "sbom.json"), "--format", "json")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    (OUT / "release_metadata.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "git_commit": commit,
                "project_version": project["project"]["version"],
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "status": "dependency-evidence-generated",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
