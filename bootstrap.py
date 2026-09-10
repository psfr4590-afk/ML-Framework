#!/usr/bin/env python3
"""Canonical Model Lab bootstrapper.

Resolves the project from this file, validates the environment, detects host
hardware, and optionally installs the declared dependencies or reconciles the
local llama.cpp toolchain. It never depends on the caller's cwd.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RECONCILER = ROOT / "scripts" / "reconcile_environment.py"
REQUIREMENTS = ROOT / "requirements.txt"
TORCH_REQUIREMENTS = ROOT / "requirements-torch.txt"
MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 14)
REQUIRED = ("yaml", "requests", "bs4", "lxml", "numpy", "tokenizers", "torch")
CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
PIP_NETWORK_OPTIONS = ("--timeout", "120", "--retries", "5")


@dataclass(frozen=True)
class HardwareProfile:
    """Host facts used for installation reporting and hardware-aware policy."""

    ram_gib: float | None = None
    cpu_name: str | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    gpu_name: str | None = None
    gpu_vram_gib: float | None = None
    nvidia_smi_available: bool = False

    @property
    def nvidia_gpu_detected(self) -> bool:
        return bool(self.gpu_name and "nvidia" in self.gpu_name.lower())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_root() -> Path:
    return ROOT


def _python_supported() -> bool:
    version = sys.version_info[:2]
    return MIN_PYTHON <= version < MAX_PYTHON_EXCLUSIVE


def _python_requirement_message() -> str:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return (
        f"Python 3.11-3.13 required; found Python {version}. "
        "Python 3.14+ is not supported because the project's dependency set "
        "has not been validated for that interpreter range."
    )


def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _run_command(command: list[str], timeout: float = 5.0) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _ram_gib() -> float | None:
    if os.name == "nt":
        output = _run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ]
        )
        if output and output.isdigit():
            return round(int(output) / (1024**3), 2)
        return None
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(pages * page_size / (1024**3), 2)
        except (OSError, ValueError):
            return None
    return None


def _windows_cpu() -> tuple[str | None, int | None, int | None]:
    if os.name != "nt":
        return platform.processor() or None, os.cpu_count(), os.cpu_count()
    output = _run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress",
        ]
    )
    if not output:
        return platform.processor() or None, None, os.cpu_count()
    try:
        data = json.loads(output)
        return (
            data.get("Name"),
            int(data["NumberOfCores"]) if data.get("NumberOfCores") is not None else None,
            int(data["NumberOfLogicalProcessors"]) if data.get("NumberOfLogicalProcessors") is not None else None,
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return platform.processor() or None, None, os.cpu_count()


def _nvidia_gpu() -> tuple[str | None, float | None, bool]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None, None, False
    output = _run_command(
        [
            executable,
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return None, None, True
    first = output.splitlines()[0].strip()
    parts = [part.strip() for part in first.split(",", 1)]
    if not parts or not parts[0]:
        return None, None, True
    vram = None
    if len(parts) == 2:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", parts[1])
        if match:
            vram = round(float(match.group(1)) / 1024, 2)
    return parts[0], vram, True


def detect_hardware() -> HardwareProfile:
    """Collect host facts without importing optional ML dependencies."""
    cpu_name, cpu_cores, cpu_threads = _windows_cpu()
    gpu_name, gpu_vram_gib, nvidia_smi_available = _nvidia_gpu()
    return HardwareProfile(
        ram_gib=_ram_gib(),
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        gpu_name=gpu_name,
        gpu_vram_gib=gpu_vram_gib,
        nvidia_smi_available=nvidia_smi_available,
    )


def torch_channel_summary(channel: str, profile: HardwareProfile) -> dict[str, Any]:
    """Describe the requested Torch channel without claiming runtime CUDA support."""
    gpu_detected = profile.nvidia_gpu_detected
    warning = None
    if channel == "default" and gpu_detected:
        warning = (
            "Default PyPI Torch was explicitly requested on an NVIDIA host. "
            "The selected wheel's CUDA runtime must be verified after installation; "
            "GPU detection alone does not prove torch.cuda.is_available()."
        )
    elif channel == "default" and not gpu_detected:
        warning = "Default PyPI Torch was explicitly requested without a detected NVIDIA GPU."
    return {
        "selected_channel": channel,
        "gpu_detected": gpu_detected,
        "cuda_install_requested": channel == "default" and gpu_detected,
        "hardware_warning": warning,
    }


def torch_runtime_status() -> dict[str, Any]:
    """Report actual Torch/CUDA runtime state, never infer it from host hardware."""
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:
        return {"installed": False, "cuda_available": False, "error": type(exc).__name__}
    cuda_available = bool(torch.cuda.is_available())
    return {
        "installed": True,
        "version": getattr(torch, "__version__", None),
        "cuda_available": cuda_available,
        "cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
        "device_count": torch.cuda.device_count() if cuda_available else 0,
    }


def _print_hardware(profile: HardwareProfile) -> None:
    print("Hardware:")
    print(f"  RAM GiB: {profile.ram_gib if profile.ram_gib is not None else 'UNKNOWN'}")
    print(f"  CPU: {profile.cpu_name or 'UNKNOWN'}")
    print(f"  CPU cores/threads: {profile.cpu_cores or 'UNKNOWN'}/{profile.cpu_threads or 'UNKNOWN'}")
    print(f"  NVIDIA GPU: {profile.gpu_name or 'NONE DETECTED'}")
    print(f"  NVIDIA VRAM GiB: {profile.gpu_vram_gib if profile.gpu_vram_gib is not None else 'UNKNOWN'}")
    print(f"  nvidia-smi: {'OK' if profile.nvidia_smi_available else 'MISSING'}")


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
    profile = detect_hardware()
    _print_hardware(profile)
    print(f"Torch channel recommendation: {'default' if profile.nvidia_gpu_detected else 'cpu'}")
    runtime = torch_runtime_status()
    print(f"Torch runtime: {'OK' if runtime['installed'] else 'MISSING'}")
    if runtime["installed"]:
        print(f"  Torch version: {runtime.get('version') or 'UNKNOWN'}")
        print(f"  CUDA available: {runtime['cuda_available']}")
        print(f"  CUDA runtime: {runtime.get('cuda_version') or 'NONE'}")
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
