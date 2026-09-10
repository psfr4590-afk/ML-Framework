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
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINT_TARGETS = [
    "command_center",
    "pipeline",
    "tests",
    "scripts",
    "run_pipeline.py",
    "run_command_center.py",
    "launch.py",
    "bootstrap.py",
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


def _native_smoke() -> int:
    """Run the bounded smoke pipeline through GGUF export and inference."""
    source = ROOT / "config" / "pipeline_config.smoke.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    config.setdefault("stages", {})["export"] = True

    with tempfile.TemporaryDirectory(prefix="model-lab-release-") as tmp:
        tmp_root = Path(tmp)
        output = tmp_root / "output"
        scratch = tmp_root / "scratch"
        config.setdefault("pipeline", {})["output_dir"] = str(output)
        config["pipeline"]["scratch_dir"] = str(scratch)
        config.setdefault("export", {})["llamacpp_dir"] = str(ROOT / "third_party" / "llama.cpp")
        config_path = tmp_root / "release_smoke.yaml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

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
                hash_key = f"{key}_sha256"
                if manifest.get(hash_key) != _sha256(card):
                    print(f"Export card hash mismatch: {key}: {card}")
                    return 2
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Invalid export manifest: {exc}")
            return 2

        if run([
            sys.executable,
            "scripts/verify_gguf.py",
            "--model",
            str(final_gguf),
            "--llamacpp-dir",
            str(ROOT / "third_party" / "llama.cpp"),
            "--manifest",
            str(manifest_path),
        ]):
            return 2

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            result = manifest.get("inference_validation", {})
            if result.get("status") != "passed" or not result.get("generated_output"):
                print("Export manifest does not contain a passing inference validation result")
                return 2
        except (OSError, ValueError, TypeError) as exc:
            print(f"Unable to read validated export manifest: {exc}")
            return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Model Lab production verification gate.")
    parser.add_argument(
        "--bootstrap-native",
        action="store_true",
        help="bootstrap pinned llama.cpp, run the bounded end-to-end export, and validate GGUF inference",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="not allowed for a production verification; retained only to produce a clear error",
    )
    args = parser.parse_args()

    if args.skip_tests:
        print("RELEASE VERIFICATION FAILED: --skip-tests is not allowed for a production verification.")
        return 2

    failures: list[str] = []
    compile_targets = ["pipeline", "command_center", "scripts", "run_pipeline.py", "run_command_center.py", "launch.py"]
    if run([sys.executable, "-m", "compileall", "-q", *compile_targets]):
        failures.append("compileall")
    if run(["ruff", "check", "--select", "F", *LINT_TARGETS]):
        failures.append("ruff")
    if run([sys.executable, "-m", "pytest", "-q"]):
        failures.append("pytest")
    if run([sys.executable, "run_pipeline.py", "--doctor"]):
        failures.append("doctor-required")

    if failures:
        print("RELEASE VERIFICATION FAILED:", ", ".join(failures))
        print("Platform:", platform.platform())
        return 2

    if not args.bootstrap_native:
        print("STATIC VERIFICATION PASSED: syntax, lint, tests, and required environment checks are green.")
        print("Native export prerequisites were not checked. Native artifact verification was not run. A production release requires --bootstrap-native.")
        return 0

    if run([sys.executable, "scripts/reconcile_environment.py", "--project-root", str(ROOT), "--ensure-llamacpp"]):
        print("RELEASE VERIFICATION FAILED: llama.cpp-bootstrap")
        print("Platform:", platform.platform())
        return 2
    print("native export prerequisites are green")
    if _native_smoke():
        print("RELEASE VERIFICATION FAILED: native export/inference")
        print("Platform:", platform.platform())
        return 2

    print("RELEASE VERIFICATION PASSED: syntax, lint, tests, doctor, native export, export cards, GGUF integrity, and inference are green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
