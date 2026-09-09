"""Pretraining loop with AMP, gradient accumulation, evaluation and checkpoints."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn

from pipeline.integrity import sha256_file
from pipeline.model_sizer import estimate_total_tokens, profile_hardware, recommend_training_profile
from pipeline.shardwriter.shard_writer import ShardDataLoader
from pipeline.trainer.model import LlamaModel, ModelConfig

log = logging.getLogger("trainer")


def cosine_lr(step: int, warmup_steps: int, lr_max: float, lr_min: float, total_steps: int) -> float:
    if step < warmup_steps:
        return lr_max * step / max(warmup_steps, 1)
    if step >= total_steps:
        return lr_min
    progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
    return lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * progress))


def save_checkpoint(model: LlamaModel, optimizer: torch.optim.Optimizer, scaler,
                    step: int, val_loss: float, cfg: dict, out_dir: Path, tag: str = ""):
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"ckpt_{tag}_{step:07d}.pt" if tag else f"ckpt_{step:07d}.pt"
    path = out_dir / name
    payload = {"step": step, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
               "scaler": scaler.state_dict(), "val_loss": val_loss,
               "model_cfg": model.cfg.to_dict(), "train_cfg": cfg}
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)
    manifest = {"schema": 1, "path": str(path), "size": path.stat().st_size,
                "sha256": sha256_file(path), "step": step, "val_loss": val_loss}
    mp = path.with_name(path.name + ".manifest.json")
    mtmp = mp.with_suffix(mp.suffix + ".tmp")
    mtmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(mtmp, mp)
    return path


def load_checkpoint(path: Path, model: LlamaModel,
                    optimizer: Optional[torch.optim.Optimizer] = None,
                    scaler=None, device: torch.device | None = None) -> int:
    if not path.exists() or path.stat().st_size < 1024:
        raise RuntimeError(f"Checkpoint missing or truncated: {path}")
    mp = path.with_name(path.name + ".manifest.json")
    if not mp.is_file():
        raise RuntimeError(f"Checkpoint integrity manifest missing: {mp}")
    meta = json.loads(mp.read_text(encoding="utf-8"))
    if int(meta.get("size", -1)) != path.stat().st_size or meta.get("sha256") != sha256_file(path):
        raise RuntimeError(f"Checkpoint integrity verification failed: {path}")
    try:
        ckpt = torch.load(path, map_location=device or "cpu", weights_only=False)
    except TypeError:
        ckpt = torch.load(path, map_location=device or "cpu")
    if not isinstance(ckpt, dict) or "model" not in ckpt or "step" not in ckpt:
        raise RuntimeError(f"Checkpoint schema invalid: {path}")
    model.load_state_dict(ckpt["model"])
    if optimizer is not None and "optimizer" in ckpt:
        optimizer.load_state_dict(ckpt["optimizer"])
    if scaler is not None and "scaler" in ckpt:
        scaler.load_state_dict(ckpt["scaler"])
    return int(ckpt["step"])


def latest_checkpoint(ckpt_dir: Path) -> Optional[Path]:
    ckpts = [p for p in sorted(ckpt_dir.glob("ckpt_*.pt"))
             if p.with_name(p.name + ".manifest.json").is_file()]
    return ckpts[-1] if ckpts else None


class Trainer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.t_cfg = cfg.get("train", {})
        self.out_dir = Path(cfg.get("pipeline", {}).get("output_dir", "output"))
        self.ckpt_dir = self.out_dir / "checkpoints"
        self.log_path = self.out_dir / "logs" / "train.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        target = str(self.log_path.resolve())
        if not any(getattr(h, "_model_lab_path", None) == target for h in log.handlers):
            handler = logging.FileHandler(self.log_path, encoding="utf-8")
            handler._model_lab_path = target
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            log.addHandler(handler)

    def run(self):
        t = dict(self.t_cfg)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if device.type == "cpu" and not bool(t.get("allow_cpu_training", False)):
            raise RuntimeError("CUDA is unavailable and allow_cpu_training=false; refusing accidental CPU pretraining")

        if bool(t.get("auto_size", False)):
            hardware = profile_hardware()
            shard_dir = Path(t.get("shard_dir", self.out_dir / "shards"))
            try:
                total_tokens = estimate_total_tokens(shard_dir)
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                total_tokens = None
            shard_cfg = self.cfg.get("shard", {})
            max_seq_len = shard_cfg.get("sequence_length")
            profile = recommend_training_profile(
                hardware,
                total_tokens=total_tokens,
                configured_steps=int(t.get("total_steps", 100_000)),
                target_training_hours=float(t["target_training_hours"]) if t.get("target_training_hours") is not None else None,
                observed_tokens_per_sec=float(t["observed_tokens_per_sec"]) if t.get("observed_tokens_per_sec") is not None else None,
                max_seq_len=int(max_seq_len) if max_seq_len is not None else None,
            )
            t.update({
                "model_preset": profile.model_preset,
                "seq_len": profile.seq_len,
                "batch_size": profile.batch_size,
                "grad_accum_steps": profile.grad_accum_steps,
                "eval_batches": profile.eval_batches,
                "eval_every_steps": profile.eval_every_steps,
                "checkpoint_every_steps": profile.checkpoint_every_steps,
                "total_steps": profile.recommended_steps or int(t.get("total_steps", 100_000)),
                "_hardware_profile": hardware.to_dict(),
                "_training_profile": profile.to_dict(),
            })
            log.info("Auto-sized training profile | hardware=%s | profile=%s", hardware.to_dict(), profile.to_dict())

        preset = t.get("model_preset", "117M")
        model_cfg = ModelConfig.from_preset(preset)
        model_cfg.vocab_size = int(t.get("vocab_size", 32000))
        model_cfg.seq_len = int(t.get("seq_len", 1024))
        model_cfg.dropout = float(t.get("dropout", 0.0))
        model = LlamaModel(model_cfg).to(device)

        decay, no_decay = [], []
        for name, p in model.named_parameters():
            if not p.requires_grad:
                continue
            (no_decay if (p.dim() < 2 or "norm" in name or "bias" in name or "embed" in name) else decay).append(p)
        optimizer = torch.optim.AdamW(
            [{"params": decay, "weight_decay": float(t.get("weight_decay", 0.1))},
             {"params": no_decay, "weight_decay": 0.0}],
            lr=float(t.get("lr_max", 3e-4)), betas=(0.9, 0.95), fused=False)
        scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))
        self.amp_dtype = torch.float16

        total_steps = int(t.get("total_steps", 100_000))
        warmup_steps = int(t.get("warmup_steps", 2_000))
        batch_size = int(t.get("batch_size", 1))
        grad_accum = int(t.get("grad_accum_steps", 16))
        grad_clip = float(t.get("grad_clip", 1.0))
        eval_every = max(1, int(t.get("eval_every_steps", 500)))
        ckpt_every = max(1, int(t.get("checkpoint_every_steps", 1000)))
        eval_batches = max(1, int(t.get("eval_batches", 20)))
        seq_len = model_cfg.seq_len
        dtype = np.uint32 if str(t.get("shard_dtype", "uint16")) == "uint32" else np.uint16
        shard_dir = Path(t.get("shard_dir", self.out_dir / "shards"))

        if max_seq_len := self.cfg.get("shard", {}).get("sequence_length"):
            if seq_len > int(max_seq_len):
                raise RuntimeError(
                    f"Training seq_len={seq_len} exceeds shard sequence_length={int(max_seq_len)}; "
                    "rebuild shards or enable a compatible auto-size profile"
                )

        train_loader = ShardDataLoader(shard_dir, "train", seq_len, dtype=dtype)
        val_loader = ShardDataLoader(shard_dir, "val", seq_len, dtype=dtype)

        start_step, best_val = 0, float("inf")
        if bool(t.get("resume", True)):
            ckpt = latest_checkpoint(self.ckpt_dir)
            if ckpt:
                start_step = load_checkpoint(ckpt, model, optimizer, scaler, device)
                try:
                    payload = torch.load(ckpt, map_location="cpu", weights_only=False)
                except TypeError:
                    payload = torch.load(ckpt, map_location="cpu")
                best_val = float(payload.get("val_loss", best_val))

        metrics_path = self.out_dir / "logs" / "metrics.jsonl"
        metrics = open(metrics_path, "a", encoding="utf-8")
        model.train()
        optimizer.zero_grad(set_to_none=True)
        start_time = time.time()
        step = start_step

        try:
            while step < total_steps:
                lr = cosine_lr(step, warmup_steps, float(t.get("lr_max", 3e-4)),
                               float(t.get("lr_min", 3e-5)), total_steps)
                for group in optimizer.param_groups:
                    group["lr"] = lr
                accum_loss = 0.0
                for _ in range(grad_accum):
                    x, y = train_loader.next_batch(batch_size)
                    x, y = x.to(device), y.to(device)
                    with torch.autocast(device_type=device.type, dtype=self.amp_dtype, enabled=(device.type == "cuda")):
                        _, loss = model(x, y)
                        loss = loss / grad_accum
                    scaler.scale(loss).backward()
                    accum_loss += loss.item()
                scaler.unscale_(optimizer)
                grad_norm = nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                step += 1

                if step % 10 == 0:
                    elapsed = max(time.time() - start_time, 1e-6)
                    tok_s = (step - start_step) * batch_size * grad_accum * seq_len / elapsed
                    metrics.write(json.dumps({"step": step, "train_loss": accum_loss,
                                              "lr": lr, "grad_norm": float(grad_norm),
                                              "tokens_per_sec": tok_s}) + "\n")
                    metrics.flush()

                if step % eval_every == 0:
                    val_loss = self._eval(model, val_loader, device, eval_batches, batch_size)
                    metrics.write(json.dumps({"step": step, "val_loss": val_loss,
                                              "val_ppl": math.exp(min(val_loss, 20))}) + "\n")
                    metrics.flush()
                    model.train()
                    if val_loss < best_val:
                        best_val = val_loss
                        save_checkpoint(model, optimizer, scaler, step, val_loss, t, self.ckpt_dir, tag="best")

                if step % ckpt_every == 0:
                    save_checkpoint(model, optimizer, scaler, step, best_val, t, self.ckpt_dir)
                    self._prune_checkpoints(self.ckpt_dir, keep=3)

            val_loss = self._eval(model, val_loader, device, eval_batches, batch_size)
            save_checkpoint(model, optimizer, scaler, step, val_loss, t, self.ckpt_dir, tag="final")
            return model, step
        finally:
            metrics.close()

    @torch.no_grad()
    def _eval(self, model, loader, device, n_batches, batch_size) -> float:
        model.eval()
        losses = []
        for _ in range(n_batches):
            x, y = loader.next_batch(batch_size)
            x, y = x.to(device), y.to(device)
            with torch.autocast(device_type=device.type, dtype=self.amp_dtype, enabled=(device.type == "cuda")):
                _, loss = model(x, y)
            losses.append(float(loss.item()))
        return float(np.mean(losses))

    def _prune_checkpoints(self, ckpt_dir: Path, keep: int = 3):
        checkpoints = sorted(ckpt_dir.glob("ckpt_[0-9]*.pt"))
        for old in checkpoints[:-keep]:
            old.unlink(missing_ok=True)
            old.with_name(old.name + ".manifest.json").unlink(missing_ok=True)


__all__ = ["Trainer", "cosine_lr", "save_checkpoint", "load_checkpoint", "latest_checkpoint"]
