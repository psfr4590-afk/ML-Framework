"""
orchestrator.py — Wires all pipeline stages together.

Stage flow:
  crawl → clean → embed_dedup → weight → tokenize → shard

Each stage reads/writes JSONL in scratch/ and can be resumed independently.
Run with --stage=all or --stage=crawl|clean|dedup|weight|tokenize|shard.
"""

from __future__ import annotations

# Canonical implementation lives in the supplied Model Lab 1.3.0 delivery.
# This repository import pass restores the full implementation incrementally.
