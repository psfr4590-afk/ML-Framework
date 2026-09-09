"""Capability-aware target-machine checks.

This module intentionally has no tkinter import at module collection time so
portable CI and Termux can collect the test suite safely.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WINDOWS_ONLY = pytest.mark.skipif(platform.system() != "Windows", reason="requires target Windows machine")
CI_UNSUPPORTED_DISPLAY = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true",
    reason="GitHub-hosted Windows runners use a virtual 1024x768 display",
)

@WINDOWS_ONLY
def test_python_is_supported_target_version():
    assert sys.version_info >= (3, 11), sys.version

@WINDOWS_ONLY
def test_tkinter_available():
    tk = pytest.importorskip("tkinter")
    root = tk.Tk(); root.withdraw(); root.destroy()

@WINDOWS_ONLY
@CI_UNSUPPORTED_DISPLAY
def test_target_resolution_is_1760x990_or_larger():
    tk = pytest.importorskip("tkinter")
    root = tk.Tk(); root.withdraw()
    try:
        width, height = root.winfo_screenwidth(), root.winfo_screenheight()
    finally:
        root.destroy()
    assert width >= 1760 and height >= 990, f"Detected {width}x{height}"

@WINDOWS_ONLY
def test_required_executables_are_on_path():
    missing = [name for name in ("python", "git", "cmake") if shutil.which(name) is None]
    assert not missing, missing

@WINDOWS_ONLY
def test_nvidia_smi_is_available_when_gpu_verification_is_requested():
    path = shutil.which("nvidia-smi")
    if path is None:
        pytest.skip("nvidia-smi unavailable; GPU may be absent")
    result = subprocess.run([path, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()

@WINDOWS_ONLY
def test_cuda_pytorch_status_is_recorded_not_assumed():
    torch = pytest.importorskip("torch")
    assert hasattr(torch, "cuda")
    _ = torch.cuda.is_available()

@WINDOWS_ONLY
def test_command_center_entrypoint_can_start_and_report_health():
    import time
    import urllib.request
    proc = subprocess.Popen([sys.executable, str(ROOT / "run_command_center.py"), "--no-browser"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/api/system", timeout=1) as response:
                    assert response.status == 200
                    return
            except Exception:
                time.sleep(0.25)
        pytest.fail("Command Center did not become healthy within 20 seconds")
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()

@WINDOWS_ONLY
def test_root_launcher_targets_desktop_ui():
    launcher = (ROOT / "launch.py").read_text(encoding="utf-8")
    assert "UI_ENTRYPOINT = ROOT / \"ui\" / \"app.py\"" in launcher
    assert "run_command_center.py" not in launcher
