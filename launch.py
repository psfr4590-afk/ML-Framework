from __future__ import annotations
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def main() -> int:
    backend = ROOT / "run_command_center.py"
    if not backend.exists(): raise SystemExit("run_command_center.py is missing")
    return subprocess.call([sys.executable, str(backend)])
if __name__ == "__main__": raise SystemExit(main())
