#!/usr/bin/env python3
"""CLI entry point for the pretrain data pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STAGES = ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]


def _load_cli_dataset_groups(config_path: Path) -> list[dict]:
    """Load dataset-group metadata without constructing a pipeline."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    configured = config.get("crawl", {}).get("dataset_groups_file", "config/dataset_groups.yaml")
    groups_path = Path(configured)
    if not groups_path.is_absolute():
        groups_path = ROOT / groups_path
    if not groups_path.is_file():
        return [{"id": "default", "name": "default"}]
    payload = yaml.safe_load(groups_path.read_text(encoding="utf-8")) or {}
    return list(payload.get("dataset_groups", []))


def _parse_requested_stages(value: str) -> list[str] | None:
    """Validate a stage selection before constructing the runtime pipeline."""
    requested = value.strip().lower()
    if requested == "all":
        return STAGES.copy()
    stages = [item.strip() for item in requested.split(",") if item.strip()]
    unknown = [stage for stage in stages if stage not in STAGES]
    if unknown or not stages:
        return None
    return stages


def main() -> int:
    parser = argparse.ArgumentParser(description="Pretraining data and model pipeline")
    parser.add_argument("--config", default="config/pipeline_config.yaml")
    parser.add_argument("--stages", default="all")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dataset-group", default=None)
    parser.add_argument("--dataset-id", type=int, default=None)
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--hardware-report", action="store_true", help="include detected hardware and training profile in doctor output")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--list-stages", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--web", action="store_true")
    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.doctor:
        from pipeline.doctor import run_doctor
        ok, checks = run_doctor(ROOT)
        print("Model Lab Doctor")
        for check in checks:
            marker = "PASS" if check["ok"] else ("WARN" if not check["required"] else "FAIL")
            print(f"[{marker}] {check['name']}: {check['detail']}")
        if args.hardware_report:
            from pipeline.model_sizer import profile_hardware, recommend_training_profile
            hardware = profile_hardware()
            profile = recommend_training_profile(hardware)
            print("Hardware Report")
            print(json.dumps({"hardware": hardware.to_dict(), "recommendation": profile.to_dict()}, indent=2, sort_keys=True))
        return 0 if ok else 2

    if args.list_stages:
        descriptions = {
            "crawl": "Crawl configured sources",
            "clean": "Normalize, filter, and exact-deduplicate",
            "dedup": "Semantic near-dedup",
            "weight": "Apply source/content weighting",
            "tokenize": "Train tokenizer",
            "shard": "Write binary training shards",
            "train": "Train the configured model",
            "export": "Export HF/GGUF/Ollama artifacts",
        }
        print("Available stages:")
        for stage in STAGES:
            print(f"  {stage:<12} {descriptions[stage]}")
        return 0

    os.chdir(ROOT)
    if args.web:
        try:
            import uvicorn
            from command_center.config import load_pipeline_config
            ccfg = load_pipeline_config().get("command_center", {})
            uvicorn.run(
                "command_center.web:app",
                host=ccfg.get("host", "127.0.0.1"),
                port=int(ccfg.get("port", 8000)),
                reload=False,
            )
            return 0
        except ImportError as exc:
            print(f"Command center dependencies are missing: {exc}")
            return 1

    config = Path(args.config)
    if not config.is_absolute():
        config = ROOT / config
    if not config.is_file():
        print(f"Config not found: {config}")
        return 1

    if args.list_groups:
        print("Configured dataset groups:")
        for group in _load_cli_dataset_groups(config):
            print(f"  {group.get('id', ''):<32} {group.get('name', '')}")
        return 0

    stages = _parse_requested_stages(args.stages)
    if stages is None:
        requested = args.stages.strip().lower()
        unknown = [item.strip() for item in requested.split(",") if item.strip() and item.strip() not in STAGES]
        detail = unknown if unknown else [requested or "<empty>"]
        print(f"Unknown stages: {detail}. Valid: {STAGES}")
        return 1

    from pipeline.orchestrator import Pipeline
    pipeline = Pipeline(str(config), dataset_id=args.dataset_id)
    if args.no_resume:
        pipeline._resume = False
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    try:
        for stage in stages:
            pipeline.run(stage, dataset_group=args.dataset_group)
    except KeyboardInterrupt:
        print("\nInterrupted. Atomic artifacts remain intact; rerun with resume enabled.")
        return 130
    except Exception as exc:
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
