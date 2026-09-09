"""Hardware and corpus aware training-profile selection.

This module deliberately uses conservative preset tiers rather than pretending
that a single parameter-to-memory formula can predict real training memory.
"""
from __future__ import annotations

import math
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HardwareProfile:
    platform: str
    cpu_cores: int
    available_ram_gb: float | None
    gpu_count: int
    gpu_memory_gb: float
    gpu_name: str | None
    cuda_available: bool

    @property
    def tier(self) -> str:
        if not self.cuda_available or self.gpu_count == 0:
            return "cpu"
        vram = self.gpu_memory_gb
        if vram < 4:
            return "gpu_<4gb"
        if vram < 6:
            return "gpu_4_6gb"
        if vram < 10:
            return "gpu_6_10gb"
        if vram < 20:
            return "gpu_10_20gb"
        return "gpu_20gb_plus"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["tier"] = self.tier
        return data


@dataclass(frozen=True)
class TrainingProfile:
    name: str
    model_preset: str
    seq_len: int
    batch_size: int
    grad_accum_steps: int
    eval_batches: int
    eval_every_steps: int
    checkpoint_every_steps: int
    precision: str
    reason: str
    recommended_steps: int | None = None
    estimated_hours: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _available_ram_gb() -> float | None:
    try:
        if platform.system() == "Windows":
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullAvailPhys / (1024**3)
        else:
            pages = os.sysconf("SC_AVPHYS_PAGES")
            size = os.sysconf("SC_PAGE_SIZE")
            return pages * size / (1024**3)
    except Exception:
        return None
    return None


def profile_hardware() -> HardwareProfile:
    gpu_count = 0
    gpu_memory_gb = 0.0
    gpu_name = None
    cuda_available = False
    try:
        import torch
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            gpu_count = int(torch.cuda.device_count())
            if gpu_count:
                props = torch.cuda.get_device_properties(0)
                gpu_memory_gb = float(props.total_memory) / (1024**3)
                gpu_name = str(props.name)
    except Exception:
        pass
    return HardwareProfile(
        platform=platform.platform(),
        cpu_cores=os.cpu_count() or 1,
        available_ram_gb=_available_ram_gb(),
        gpu_count=gpu_count,
        gpu_memory_gb=gpu_memory_gb,
        gpu_name=gpu_name,
        cuda_available=cuda_available,
    )


def estimate_total_tokens(shard_dir: str | Path) -> int:
    """Estimate exact token count from shard bytes using the shard manifest."""
    root = Path(shard_dir)
    manifest = root / "shards.manifest.json"
    if manifest.is_file():
        import json
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        dtype = str(payload.get("dtype", "uint16"))
        itemsize = 4 if dtype == "uint32" else 2
        return sum(int(item.get("size", 0)) // itemsize for item in payload.get("files", []))
    files = sorted(root.glob("shard_*_*.bin"))
    if not files:
        raise FileNotFoundError(f"No shard files found in {root}")
    return sum(p.stat().st_size // 2 for p in files)


def recommend_training_profile(
    hardware: HardwareProfile,
    total_tokens: int | None = None,
    configured_steps: int = 100_000,
    target_training_hours: float | None = None,
    observed_tokens_per_sec: float | None = None,
) -> TrainingProfile:
    """Choose a conservative preset and training geometry for the host."""
    profiles = {
        "cpu": TrainingProfile("cpu-safe", "85M", 256, 1, 32, 2, 100, 250, "fp32", "CPU-only host; smallest preset and short context reduce memory pressure"),
        "gpu_<4gb": TrainingProfile("gpu-sub4gb", "85M", 256, 1, 32, 2, 100, 250, "fp16", "Very small VRAM budget; prioritize viability over throughput"),
        "gpu_4_6gb": TrainingProfile("gpu-4-6gb", "85M", 512, 1, 32, 4, 200, 500, "fp16", "4–6 GB VRAM; 85M preset with reduced context"),
        "gpu_6_10gb": TrainingProfile("gpu-6-10gb", "117M", 512, 1, 32, 4, 250, 500, "fp16", "6–10 GB VRAM; 117M is viable with reduced context"),
        "gpu_10_20gb": TrainingProfile("gpu-10-20gb", "117M", 1024, 1, 16, 8, 500, 1000, "fp16", "10–20 GB VRAM; full 1K context on the 117M preset"),
        "gpu_20gb_plus": TrainingProfile("gpu-20gb-plus", "360M", 1024, 1, 16, 8, 500, 1000, "fp16", "20+ GB VRAM; 360M remains substantially below workstation-class models"),
    }
    base = profiles[hardware.tier]
    steps = max(1, int(configured_steps))
    if total_tokens is not None and total_tokens > 0:
        tokens_per_step = base.batch_size * base.grad_accum_steps * base.seq_len
        corpus_steps = max(1, math.ceil(total_tokens / tokens_per_step))
        steps = min(steps, corpus_steps)
    hours = None
    if target_training_hours is not None and target_training_hours > 0 and observed_tokens_per_sec and observed_tokens_per_sec > 0:
        steps_for_target = int(target_training_hours * 3600 * observed_tokens_per_sec / (base.batch_size * base.grad_accum_steps * base.seq_len))
        if steps_for_target > 0:
            steps = min(steps, steps_for_target)
        hours = (steps * base.batch_size * base.grad_accum_steps * base.seq_len) / observed_tokens_per_sec / 3600
    return TrainingProfile(**{**base.to_dict(), "recommended_steps": steps, "estimated_hours": hours})


__all__ = ["HardwareProfile", "TrainingProfile", "profile_hardware", "estimate_total_tokens", "recommend_training_profile"]
