#!/usr/bin/env python3
"""Deterministic production verification for Model Lab."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pipeline.integrity import write_manifest
from pipeline.types import Document

ROOT = Path(__file__).resolve().parents[1]
LINT_TARGETS = [
    "command_center", "pipeline", "tests", "scripts", "ui",
    "run_pipeline.py", "run_command_center.py", "launch.py", "bootstrap.py",
]


def run(cmd: list[str]) -> int:
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_local_smoke_input(scratch: Path) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    corpus = scratch / "04_weighted.jsonl"
    docs = []
    for index in range(32):
        docs.append(Document(
            doc_id=f"release-smoke-{index:03d}",
            url=f"file://release-smoke/{index}",
            source="local-release-fixture",
            title="Deterministic local release fixture",
            text=("A deterministic local training fixture validates tokenization, sharding, training, "
                   "GGUF export, artifact integrity, and native inference without depending on the public Internet. " * 8).strip(),
            language="en",
            content_type="text/plain",
            domain="local.release.fixture",
            final_weight=1.0,
            meta={"release_fixture": True},
        ))
    corpus.write_text("".join(json.dumps(doc.to_jsonl(), sort_keys=True) + "\n" for doc in docs), encoding="utf-8")
    write_manifest(corpus, kind="weight", rows=len(docs), provenance={"schema": 1, "fixture": "local-release"})


def _write_smoke_source_manifest(tmp_root: Path) -> None:
    path = tmp_root / "source_manifest.json"
    path.write_text(json.dumps({
        "schema": 1,
        "retrieval_started_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_completed_at": datetime.now(timezone.utc).isoformat(),
        "sources": [{"kind": "local_fixture", "identifier": "local-release-fixture", "revision": "embedded", "license": "project-test-fixture", "raw_source_sha256": None}],
        "rights_note": "Deterministic test fixture only; not an external training source.",
    }, indent=2) + "\n", encoding="utf-8")


def _validate_source_manifest(path: Path) -> None:
    required_top_level = {"schema", "retrieval_started_at", "retrieval_completed_at", "sources", "rights_note"}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not required_top_level <= set(data):
        raise RuntimeError("Source manifest is missing required top-level metadata")
    if int(data["schema"]) != 1 or not isinstance(data["sources"], list):
        raise RuntimeError("Source manifest schema is invalid")
    required_source = {"kind", "identifier", "revision", "license", "raw_source_sha256"}
    for source in data["sources"]:
        if not isinstance(source, dict) or not required_source <= set(source):
            raise RuntimeError("Source manifest source entry is incomplete")
        digest = source["raw_source_sha256"]
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower())):
            raise RuntimeError("Source manifest raw_source_sha256 is invalid")


def _native_smoke() -> int:
    """Run a bounded, network-free smoke pipeline through GGUF export and inference."""
    source = ROOT / "config" / "pipeline_config.smoke.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    config["stages"] = {"crawl": False, "clean": False, "semantic_dedup": False, "weight": False, "tokenize": True, "shard": True, "train": True, "export": True}

    with tempfile.TemporaryDirectory(prefix="model-lab-release-") as tmp:
        tmp_root = Path(tmp)
        output = tmp_root / "output"
        scratch = tmp_root / "scratch"
        config.setdefault("pipeline", {})["output_dir"] = str(output)
        config["pipeline"]["scratch_dir"] = str(scratch)
        config["pipeline"]["resume"] = False
        config.setdefault("export", {})["llamacpp_dir"] = str(ROOT / "third_party" / "llama.cpp")
        config_path = tmp_root / "release_smoke.yaml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        _write_local_smoke_input(scratch)
        _write_smoke_source_manifest(tmp_root)
        try:
            _validate_source_manifest(tmp_root / "source_manifest.json")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            print(f"Invalid smoke source manifest: {exc}")
            return 2

        if run([sys.executable, "run_pipeline.py", "--config", str(config_path), "--no-resume"]):
            return 2

        manifest_path = output / "gguf" / "export_manifest.json"
        if not manifest_path.is_file():
            print(f"Missing export manifest: {manifest_path}")
            return 2
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            final_gguf = Path(manifest["final_gguf"])
            if not final_gguf.is_file() or final_gguf.stat().st_size <= 0:
                print(f"Missing final GGUF artifact: {final_gguf}")
                return 2
            for key in ("dataset_card", "model_card"):
                card = Path(manifest[key])
                if not card.is_file() or card.stat().st_size <= 0:
                    print(f"Missing export card: {key}: {card}")
                    return 2
                if manifest.get(f"{key}_sha256") != _sha256(card):
                    print(f"Export card hash mismatch: {key}: {card}")
                    return 2
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Invalid export manifest: {exc}")
            return 2

        if run([sys.executable, "scripts/verify_gguf.py", "--model", str(final_gguf), "--llamacpp-dir", str(ROOT / "third_party" / "llama.cpp"), "--manifest", str(manifest_path)]):
            return 2
        try:
            result = json.loads(manifest_path.read_text(encoding="utf-8")).get("inference_validation", {})
            if result.get("status") != "passed" or not result.get("generated_output"):
                print("Export manifest does not contain a passing inference validation result")
                return 2
        except (OSError, ValueError, TypeError) as exc:
            print(f"Unable to read validated export manifest: {exc}")
            return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Model Lab production verification gate.")
    parser.add_argument("--bootstrap-native", action="store_true", help="bootstrap pinned llama.cpp and validate native GGUF inference")
    parser.add_argument("--skip-tests", action="store_true", help="not allowed for production verification")
    args = parser.parse_args()
    if args.skip_tests:
        print("RELEASE VERIFICATION FAILED: --skip-tests is not allowed for a production verification.")
        return 2

    failures: list[str] = []
    compile_targets = ["pipeline", "command_center", "scripts", "ui", "run_pipeline.py", "run_command_center.py", "launch.py"]
    if run([sys.executable, "-m", "compileall", "-q", *compile_targets]): failures.append("compileall")
    if run(["ruff", "check", "--select", "F", *LINT_TARGETS]): failures.append("ruff")
    evidence = ROOT / "release-evidence"
    evidence.mkdir(exist_ok=True)
    if run([sys.executable, "-m", "pytest", "-q", "--cov-report=json:release-evidence/coverage.json"]): failures.append("pytest")
    if run([sys.executable, "run_pipeline.py", "--doctor"]): failures.append("doctor-required")
    if failures:
        print("RELEASE VERIFICATION FAILED:", ", ".join(failures)); print("Platform:", platform.platform()); return 2

    if not args.bootstrap_native:
        print("STATIC VERIFICATION PASSED: syntax, lint, coverage, tests, and required environment checks are green.")
        print("Native artifact verification was not run. A production release requires --bootstrap-native.")
        return 0

    if run([sys.executable, "scripts/reconcile_environment.py", "--project-root", str(ROOT), "--ensure-llamacpp"]):
        print("RELEASE VERIFICATION FAILED: llama.cpp-bootstrap"); print("Platform:", platform.platform()); return 2
    print("native export prerequisites are green")
    if _native_smoke():
        print("RELEASE VERIFICATION FAILED: native export/inference"); print("Platform:", platform.platform()); return 2
    print("RELEASE VERIFICATION PASSED: syntax, lint, coverage, tests, doctor, network-free native export, export cards, GGUF integrity, and inference are green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
