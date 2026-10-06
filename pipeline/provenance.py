"""Configuration identity and artifact lineage helpers.

Phase 1 deliberately separates configuration identities.  The historical
pipeline_config_sha256 remains available as legacy evidence, but it is not
used as the identity of every downstream artifact.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any


CONFIG_SECTIONS = {
    "dataset": ("crawl", "clean", "dedup", "weight"),
    "tokenizer": ("tokenizer",),
    "shard": ("shard",),
    "train": ("train",),
    "model": ("train",),
    "export": ("export",),
}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def config_identities(cfg: dict[str, Any], *, pipeline_sha256: str | None = None,
                      source_definition_hashes: dict[str, str | None] | None = None) -> dict[str, Any]:
    """Return independent immutable configuration identities for a run."""
    identities: dict[str, Any] = {}
    for name, sections in CONFIG_SECTIONS.items():
        payload = {section: cfg.get(section, {}) for section in sections}
        if name == "model":
            train = dict(payload.get("train") or {})
            payload["train"] = {
                key: train.get(key)
                for key in ("model_preset", "vocab_size", "seq_len", "dropout")
                if key in train
            }
        identities[f"{name}_config_sha256"] = stable_hash(payload)

    identities["source_definition_sha256"] = stable_hash(source_definition_hashes or {})
    if pipeline_sha256:
        identities["pipeline_config_sha256"] = pipeline_sha256
    return identities


def new_run_id() -> str:
    return uuid.uuid4().hex


def artifact_id(kind: str, content_sha256: str) -> str:
    return f"{kind}:{content_sha256}"


def snapshot_configs(root: Path, cfg: dict[str, Any], identities: dict[str, Any],
                     *, config_path: Path | None = None) -> dict[str, str]:
    """Persist immutable JSON snapshots keyed by their content identity."""
    directory = root / "provenance" / "configs"
    directory.mkdir(parents=True, exist_ok=True)
    snapshots: dict[str, str] = {}

    for name, sections in CONFIG_SECTIONS.items():
        sha = identities[f"{name}_config_sha256"]
        payload = {section: cfg.get(section, {}) for section in sections}
        if name == "model":
            train = dict(payload.get("train") or {})
            payload["train"] = {
                key: train.get(key)
                for key in ("model_preset", "vocab_size", "seq_len", "dropout")
                if key in train
            }
        path = directory / f"{name}-{sha}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        snapshots[name] = str(path.relative_to(root)).replace("\\", "/")

    if config_path is not None and config_path.is_file():
        legacy_sha = identities.get("pipeline_config_sha256")
        if legacy_sha:
            path = directory / f"pipeline-legacy-{legacy_sha}.yaml"
            if not path.exists():
                path.write_bytes(config_path.read_bytes())
            snapshots["pipeline_legacy"] = str(path.relative_to(root)).replace("\\", "/")
    return snapshots
