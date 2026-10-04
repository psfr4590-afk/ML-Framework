#!/usr/bin/env python3
"""Run the native release gate while recording the actual host hardware."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"unavailable: {exc}"
    return (result.stdout or result.stderr).strip()


def main() -> int:
    print("TARGET HARDWARE RELEASE VERIFICATION")
    print("platform:", platform.platform())
    print("python:", platform.python_version())
    print("machine:", platform.machine())
    print("processor:", platform.processor())
    if sys.platform == "win32":
        print("memory:", _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"]))
        print("gpu:", _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | Format-List | Out-String)"]))
    else:
        print("memory:", _run(["python", "-c", "import os; print(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'))"]))
        print("gpu:", _run(["bash", "-lc", "command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true"]))
    print("llama-cli:", shutil.which("llama-cli") or "not on PATH; release bootstrap will resolve the pinned toolchain")
    evidence = ROOT / "release-evidence"
    evidence.mkdir(exist_ok=True)
    report = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "llama_cli": shutil.which("llama-cli"),
        "runner_is_target_hardware": False,
    }
    report["native_release_gate_exit_code"] = subprocess.run(
        [sys.executable, "scripts/verify_release.py", "--bootstrap-native"], cwd=ROOT, check=False
    ).returncode
    report["status"] = "passed" if report["native_release_gate_exit_code"] == 0 else "failed"
    (evidence / "target_hardware_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(report["native_release_gate_exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
