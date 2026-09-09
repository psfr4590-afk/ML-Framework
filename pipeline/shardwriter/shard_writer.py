"""
shard_writer.py — Tokenizes the weighted corpus and writes binary training shards.

Output format: numpy uint16 (or uint32) arrays, one file per shard.
  shard_00000_train.bin, shard_00001_train.bin, ..., shard_00042_val.bin

Each shard is a flat array of token IDs. The training loop reads these via
np.memmap for bounded-memory streaming.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import tempfile
from pathlib import Path
from typing import Iterator

import numpy as np

log = logging.getLogger("shard_writer")


class ShardWriter:
    def __init__(self, cfg: dict, tokenizer):
        self._cfg = cfg
        self._tok = tokenizer
        self._seq_len = cfg.get("sequence_length", 1024)
        self._dtype = np.uint16 if cfg.get("dtype", "uint16") == "uint16" else np.uint32
        self._shard_size = cfg.get("shard_size_tokens", 10_000_000)
        self._out_dir = Path(cfg.get("output_dir", "output/shards")).resolve()
        self._val_frac = cfg.get("val_fraction", 0.005)
        self._shuffle = cfg.get("shuffle_docs", True)
        self._seed = int(cfg.get("seed", 42))
        self._shuffle_buffer = max(1, int(cfg.get("shuffle_buffer_size", 10000)))
        self._out_dir.mkdir(parents=True, exist_ok=True)

        vocab = self._tok.get_vocab()
        self._vocab_size = len(vocab)
        max_id = np.iinfo(self._dtype).max
        if self._vocab_size - 1 > max_id:
            raise ValueError(
                f"Tokenizer vocab {self._vocab_size} exceeds {self._dtype.__name__} capacity {max_id + 1}"
            )
        self._eos_id = vocab.get("<|eos|>", vocab.get("</s>", 2))
        if self._eos_id > max_id:
            raise ValueError(f"EOS token id {self._eos_id} exceeds {self._dtype.__name__} capacity {max_id + 1}")

        self.stats = {
            "docs_processed": 0,
            "total_tokens": 0,
            "shards_written": 0,
            "train_shards": 0,
            "val_shards": 0,
        }

    def _tokenize_doc(self, text: str) -> list[int]:
        ids = list(self._tok.encode(text).ids)
        if ids:
            ids.append(self._eos_id)
        return ids

    def _write_shard(self, tokens: list[int], shard_idx: int, split: str) -> Path:
        arr = np.asarray(tokens)
        max_id = np.iinfo(self._dtype).max
        if arr.size and (int(arr.min()) < 0 or int(arr.max()) > max_id):
            raise ValueError(
                f"Token id out of range for {self._dtype.__name__}: min={arr.min()} max={arr.max()}"
            )
        arr = arr.astype(self._dtype, copy=False)
        name = f"shard_{shard_idx:05d}_{split}.bin"
        path = self._out_dir / name
        fd, tmp = tempfile.mkstemp(prefix=name + ".", suffix=".tmp", dir=self._out_dir)
        try:
            with os.fdopen(fd, "wb") as f:
                arr.tofile(f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

        self.stats["shards_written"] += 1
        if split == "train":
            self.stats["train_shards"] += 1
        else:
            self.stats["val_shards"] += 1
        log.info("Wrote %s | tokens=%d size=%.1fMB", path, len(tokens), arr.nbytes / 1024 / 1024)
        return path

    def _iter_texts(self, jsonl_path: Path, split: str) -> Iterator[str]:
        threshold = int(self._val_frac * 1_000_000)
        if split == "val" and threshold <= 0:
            return
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"Shard input integrity failure at {jsonl_path}:{line_no}: {exc}"
                    ) from exc
                if not isinstance(obj, dict):
                    raise RuntimeError(f"Shard input record {line_no} is not an object")
                text = str(obj.get("text", "") or "")
                if not text:
                    continue
                key = str(obj.get("doc_id") or f"line:{line_no}")
                bucket = int.from_bytes(
                    hashlib.sha256(f"{self._seed}:{key}".encode("utf-8")).digest()[:4],
                    "big",
                ) % 1_000_000
                if (bucket < threshold) == (split == "val"):
                    yield text

    def _shuffled(self, texts: Iterator[str]) -> Iterator[str]:
        if not self._shuffle:
            yield from texts
            return
        rng = random.Random(self._seed)
        buf: list[str] = []
        for text in texts:
            buf.append(text)
            if len(buf) >= self._shuffle_buffer:
                yield buf.pop(rng.randrange(len(buf)))
        while buf:
            yield buf.pop(rng.randrange(len(buf)))

    def _write_manifest(self) -> Path:
        files = []
        for path in sorted(self._out_dir.glob("shard_*_*.bin")):
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            item = {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
            files.append(item)
        manifest = {
            "version": 1,
            "dtype": str(np.dtype(self._dtype)),
            "sequence_length": self._seq_len,
            "vocab_size": self._vocab_size,
            "files": files,
        }
        path = self._out_dir / "shards.manifest.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return path

    def write(self, jsonl_path: str | Path) -> None:
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.is_file():
            raise FileNotFoundError(jsonl_path)

        wrote_any = False
        for split in ("train", "val"):
            shard_buf: list[int] = []
            shard_idx = 0
            docs_in_split = 0
            for text in self._shuffled(self._iter_texts(jsonl_path, split)):
                ids = self._tokenize_doc(text)
                if not ids:
                    continue
                wrote_any = True
                docs_in_split += 1
                self.stats["docs_processed"] += 1
                self.stats["total_tokens"] += len(ids)
                shard_buf.extend(ids)
                while len(shard_buf) >= self._shard_size:
                    self._write_shard(shard_buf[:self._shard_size], shard_idx, split)
                    del shard_buf[:self._shard_size]
                    shard_idx += 1
            if shard_buf:
                self._write_shard(shard_buf, shard_idx, split)
            log.info("%s split: %d documents", split, docs_in_split)

        if not wrote_any:
            raise RuntimeError(f"Shard input contains no usable text: {jsonl_path}")
        if self.stats["train_shards"] == 0 or self.stats["val_shards"] == 0:
            raise RuntimeError(
                "Shard generation requires at least one train and one validation shard. "
                "Increase corpus size or adjust val_fraction/shard_size_tokens."
            )
        manifest = self._write_manifest()
        log.info("Shard manifest written: %s", manifest)
        self.print_stats()

    def print_stats(self):
        s = self.stats
        log.info(
            "ShardWriter | docs=%d tokens=%d shards=%d (train=%d val=%d)",
            s["docs_processed"], s["total_tokens"], s["shards_written"],
            s["train_shards"], s["val_shards"],
        )


class ShardDataLoader:
    """Memory-mapped loader for binary shards."""

    def __init__(self, shard_dir: str | Path, split: str, seq_len: int,
                 dtype=np.uint16, seed: int = 42):
        self._dir = Path(shard_dir)
        self._split = split
        self._seq_len = seq_len
        self._dtype = dtype
        self._rng = random.Random(seed)
        self._shards = sorted(self._dir.glob(f"shard_*_{split}.bin"))
        if not self._shards:
            raise FileNotFoundError(f"No {split} shards in {shard_dir}")

        manifest_path = self._dir / "shards.manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"Shard integrity manifest missing: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = {item["name"]: item for item in manifest.get("files", [])}
            for shard in self._shards:
                item = entries.get(shard.name)
                if not item or int(item.get("size", -1)) != shard.stat().st_size:
                    raise RuntimeError(f"Shard manifest mismatch: {shard}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(f"Invalid shard manifest: {manifest_path}") from exc

        self._rng.shuffle(self._shards)
        self._shard_idx = 0
        self._pos = 0
        self._data = self._load_shard(self._shards[0])

    def _load_shard(self, path: Path) -> np.ndarray:
        return np.memmap(path, dtype=self._dtype, mode="r")

    def next_batch(self, batch_size: int):
        import torch
        L = self._seq_len + 1
        x_list, y_list = [], []
        for _ in range(batch_size):
            attempts = 0
            while self._pos + L > len(self._data):
                self._shard_idx = (self._shard_idx + 1) % len(self._shards)
                self._data = self._load_shard(self._shards[self._shard_idx])
                self._pos = 0
                attempts += 1
                if attempts > len(self._shards):
                    raise RuntimeError(
                        f"No {self._split} shard contains at least {L} tokens; "
                        "increase corpus/shard size or reduce seq_len"
                    )
            chunk = self._data[self._pos:self._pos + L].astype(np.int64)
            x_list.append(chunk[:-1])
            y_list.append(chunk[1:])
            self._pos += self._seq_len

        return torch.from_numpy(np.stack(x_list)), torch.from_numpy(np.stack(y_list))


__all__ = ["ShardWriter", "ShardDataLoader"]
