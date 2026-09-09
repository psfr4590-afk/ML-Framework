"""Canonical desktop launcher for Model Lab."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI_ENTRYPOINT = ROOT / "ui" / "app.py"


def main() -> int:
    """Start the native desktop control surface."""
    if not UI_ENTRYPOINT.is_file():
        raise SystemExit(f"ui/app.py is missing: {UI_ENTRYPOINT}")
    return subprocess.call([sys.executable, str(UI_ENTRYPOINT)], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
