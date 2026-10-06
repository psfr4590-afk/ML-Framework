"""Preflight training benchmark and duration estimation.

The benchmark uses the real model geometry and real shard loader, but a fresh
model/optimizer, so it validates viability without mutating a training run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

from pipeline.shardwriter.shard_writer import ShardDataLoader
from pipeline.trainer.model import LlamaModel, ModelConfig


@dataclass(frozen=True)
class PreflightResult:
    viable: bool
    tokens_per_sec: float | None
    steps_per_sec: float | None
    peak_memory_gb: float | None
    gpu_utilization_percent: float | None
    benchmark_seconds: float
    warmup_steps: int
    benchmark_steps: int
    failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gpu_utilization() -> float | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        return float(out.stdout.splitlines()[0].strip())
    except ValueError:
        return None


def _make_model(train_cfg: dict[str, Any]) -> LlamaModel:
    cfg = ModelConfig.from_preset(str(train_cfg.get("model_preset", "85M")))
    cfg.vocab_size = int(train_cfg.get("vocab_size", 32000))
    cfg.seq_len = int(train_cfg.get("seq_len", 256))
    cfg.dropout = float(train_cfg.get("dropout", 0.0))
    return LlamaModel(cfg)


def run_preflight(
    train_cfg: dict[str, Any],
    shard_dir: str | Path,
    *,
    warmup_steps: int = 1,
    benchmark_steps: int = 3,
) -> PreflightResult:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    warmup_steps = max(0, int(warmup_steps))
    benchmark_steps = max(1, int(benchmark_steps))
    started = time.perf_counter()
    model = None
    optimizer = None
    try:
        model = _make_model(train_cfg).to(device)
        batch_size = max(1, int(train_cfg.get("batch_size", 1)))
        grad_accum = max(1, int(train_cfg.get("grad_accum_steps", 1)))
        seq_len = int(train_cfg.get("seq_len", model.cfg.seq_len))
        dtype_name = str(train_cfg.get("shard_dtype", "uint16"))
        import numpy as np
        dtype = np.uint32 if dtype_name == "uint32" else np.uint16
        loader = ShardDataLoader(shard_dir, "train", seq_len, dtype=dtype, seed=int(train_cfg.get("seed", 42)))
        optimizer = torch.optim.AdamW(model.parameters(), lr=float(train_cfg.get("lr_max", 3e-4)), weight_decay=0.0)
        scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))
        if device.type == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
        model.train()

        def step_once(model=model, optimizer=optimizer) -> None:
            optimizer.zero_grad(set_to_none=True)
            for _ in range(grad_accum):
                x, y = loader.next_batch(batch_size)
                x, y = x.to(device), y.to(device)
                with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=(device.type == "cuda")):
                    _, loss = model(x, y)
                    loss = loss / grad_accum
                scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

        for _ in range(warmup_steps):
            step_once()
        if device.type == "cuda":
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()

        samples: list[float] = []
        started_bench = time.perf_counter()
        for _ in range(benchmark_steps):
            step_once()
            if device.type == "cuda":
                torch.cuda.synchronize()
            util = _gpu_utilization()
            if util is not None:
                samples.append(util)
        elapsed = max(time.perf_counter() - started_bench, 1e-9)
        tokens = benchmark_steps * batch_size * grad_accum * seq_len
        tok_s = tokens / elapsed
        peak = (torch.cuda.max_memory_allocated() / (1024**3)) if device.type == "cuda" else None
        return PreflightResult(
            viable=True,
            tokens_per_sec=tok_s,
            steps_per_sec=benchmark_steps / elapsed,
            peak_memory_gb=peak,
            gpu_utilization_percent=(sum(samples) / len(samples)) if samples else None,
            benchmark_seconds=time.perf_counter() - started,
            warmup_steps=warmup_steps,
            benchmark_steps=benchmark_steps,
        )
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        if device.type == "cuda" and "out of memory" in str(exc).lower():
            torch.cuda.empty_cache()
        return PreflightResult(
            viable=False, tokens_per_sec=None, steps_per_sec=None,
            peak_memory_gb=(torch.cuda.max_memory_allocated() / (1024**3)) if device.type == "cuda" else None,
            gpu_utilization_percent=None, benchmark_seconds=time.perf_counter() - started,
            warmup_steps=warmup_steps, benchmark_steps=benchmark_steps,
            failure=f"{type(exc).__name__}: {exc}",
        )
    finally:
        del optimizer
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def estimate_duration(
    *,
    total_steps: int,
    batch_size: int,
    grad_accum_steps: int,
    seq_len: int,
    tokens_per_sec: float | None,
    eval_every_steps: int,
    eval_batches: int,
    checkpoint_every_steps: int,
    checkpoint_seconds: float = 0.0,
    eval_seconds: float = 0.0,
) -> dict[str, Any]:
    if not tokens_per_sec or tokens_per_sec <= 0:
        return {"estimated_duration_seconds": None, "estimated_completion": None}
    tokens = int(total_steps) * int(batch_size) * int(grad_accum_steps) * int(seq_len)
    training_seconds = tokens / tokens_per_sec
    eval_count = max(0, (int(total_steps) - 1) // max(1, int(eval_every_steps)))
    checkpoint_count = max(0, (int(total_steps) - 1) // max(1, int(checkpoint_every_steps)))
    total_seconds = training_seconds + eval_count * float(eval_seconds) + checkpoint_count * float(checkpoint_seconds)
    checkpoints = []
    evaluations = []
    for step in range(1, int(total_steps) + 1):
        if step % max(1, int(checkpoint_every_steps)) == 0:
            checkpoints.append({"step": step, "estimated_elapsed_seconds": round(
                (step * int(batch_size) * int(grad_accum_steps) * int(seq_len)) / tokens_per_sec,
                3,
            )})
        if step % max(1, int(eval_every_steps)) == 0:
            evaluations.append({"step": step, "estimated_elapsed_seconds": round(
                (step * int(batch_size) * int(grad_accum_steps) * int(seq_len)) / tokens_per_sec,
                3,
            )})
    return {
        "estimated_training_seconds": training_seconds,
        "estimated_duration_seconds": total_seconds,
        "estimated_eval_count": eval_count,
        "estimated_checkpoint_count": checkpoint_count,
        "estimated_checkpoint_times": checkpoints,
        "estimated_eval_times": evaluations,
        "estimated_completion": time.time() + total_seconds,
    }


def write_preflight_report(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(target)


__all__ = ["PreflightResult", "run_preflight", "estimate_duration", "write_preflight_report"]
