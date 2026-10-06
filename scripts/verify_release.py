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

NATIVE_EVIDENCE: dict[str, object] = {}

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import yaml
from pipeline.integrity import write_manifest
from pipeline.run_tracking import _git, _git_state
from pipeline.types import Document

LINT_TARGETS = ["command_center", "pipeline", "tests", "scripts", "ui", "run_pipeline.py", "run_command_center.py", "launch.py", "bootstrap.py"]
RELEASE_SMOKE_SOURCES = (("local-technical", "systems architecture, compilers, operating systems, networking, storage, and distributed computing"),("local-scientific", "physics, chemistry, biology, astronomy, mathematics, statistics, and experimental methods"),("local-engineering", "mechanical, electrical, civil, software, control systems, reliability, and manufacturing engineering"),("local-humanities", "history, literature, linguistics, philosophy, archaeology, anthropology, and cultural studies"),("local-business", "accounting, finance, economics, operations, logistics, management, markets, and entrepreneurship"),("local-geography", "cartography, climate, geology, ecology, oceans, weather, agriculture, and geographic information"),("local-medicine", "anatomy, physiology, epidemiology, diagnostics, pharmacology, public health, and clinical research"),("local-creative", "music, visual design, architecture, photography, theater, film, animation, and digital media"))


def run(cmd: list[str]) -> int:
    print("$", " ".join(map(str, cmd))); return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _write_local_smoke_input(scratch: Path, pipeline_config_sha256: str | None = None, run_id: str | None = None, config_identities: dict | None = None) -> None:
    scratch.mkdir(parents=True, exist_ok=True); corpus = scratch / "04_weighted.jsonl"; docs = []
    for source_index, (source, topic_text) in enumerate(RELEASE_SMOKE_SOURCES):
        for local_index in range(32):
            index = source_index * 32 + local_index; unique_terms = " ".join(f"{source.replace('-', '')}term{index:03d}_{suffix}" for suffix in ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot")); text = f"Deterministic {source} release fixture document {index:03d}. This local source covers {topic_text}. The verification corpus includes {unique_terms}. The fixture exercises tokenization, sharding, training, GGUF export, artifact integrity, and native inference without depending on the public Internet."
            docs.append(Document(doc_id=f"release-smoke-{index:03d}", url=f"file://release-smoke/{source}/{local_index}", source=source, title=f"Deterministic {source} release fixture", text=text, language="en", content_type="text/plain", domain=f"{source}.release.fixture", final_weight=1.0, meta={"release_fixture": True, "source_family": source, "source_index": source_index}))
    corpus.write_text("".join(json.dumps(doc.to_jsonl(), sort_keys=True) + "\n" for doc in docs), encoding="utf-8")
    provenance = {"schema": 2, "stage": "weight", "fixture": "local-release-multi-source", "source_families": len(RELEASE_SMOKE_SOURCES)}
    if pipeline_config_sha256: provenance["pipeline_config_sha256"] = pipeline_config_sha256
    if run_id: provenance["run_id"] = run_id
    if config_identities: provenance["config_identities"] = dict(config_identities)
    write_manifest(corpus, kind="weight", rows=len(docs), provenance=provenance)


def _write_smoke_source_manifest(tmp_root: Path, run_id: str, source_definition_paths: dict[str, Path]) -> None:
    path = tmp_root / "source_manifest.json"
    now = datetime.now(timezone.utc).isoformat()
    files = {name: {"path": str(value.relative_to(ROOT)).replace("\\\\", "/"), "sha256": _sha256(value)} for name, value in source_definition_paths.items()}; source_definition_sha256 = __import__("hashlib").sha256(json.dumps({name: value["sha256"] for name, value in files.items()}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    path.write_text(json.dumps({"schema": 2, "run_id": run_id, "dataset_group": "release-smoke", "retrieval_started_at": now, "retrieval_completed_at": now, "source_definition_sha256": source_definition_sha256, "source_definition_files": files, "sources": [{"kind": "local_fixture", "identifier": source, "revision": "embedded", "license": "project-test-fixture", "raw_source_sha256": None, "dataset_group": "release-smoke"} for source, _ in RELEASE_SMOKE_SOURCES], "rights_note": "Deterministic test fixtures only; not external training sources."}, indent=2) + "\n", encoding="utf-8")


def _validate_source_manifest(path: Path) -> None:
    required_top_level = {"schema", "run_id", "dataset_group", "retrieval_started_at", "retrieval_completed_at", "source_definition_sha256", "source_definition_files", "sources", "rights_note"}; data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not required_top_level <= set(data): raise RuntimeError("Source manifest is missing required top-level metadata")
    if int(data["schema"]) != 2 or not isinstance(data["sources"], list) or not data["sources"]: raise RuntimeError("Source manifest schema is invalid")
    required_source = {"kind", "identifier", "revision", "license", "raw_source_sha256", "dataset_group"}
    for source in data["sources"]:
        if not isinstance(source, dict) or not required_source <= set(source): raise RuntimeError("Source manifest source entry is incomplete")
        if source.get("dataset_group") != data["dataset_group"]: raise RuntimeError("Source manifest dataset-group identity is invalid")
        digest = source["raw_source_sha256"]
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower())): raise RuntimeError("Source manifest raw_source_sha256 is invalid")


def _native_smoke(verify_ollama: bool = False) -> int:
    source = ROOT / "config" / "pipeline_config.smoke.yaml"; config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}; config["stages"] = {"crawl": False, "clean": False, "semantic_dedup": False, "weight": False, "tokenize": True, "shard": True, "train": True, "export": True}
    with tempfile.TemporaryDirectory(prefix="model-lab-release-") as tmp:
        tmp_root = Path(tmp); output = tmp_root / "output"; scratch = tmp_root / "scratch"; config.setdefault("pipeline", {})["output_dir"] = str(output); config["pipeline"]["scratch_dir"] = str(scratch); config["pipeline"]["resume"] = False; config.setdefault("export", {})["llamacpp_dir"] = str(ROOT / "third_party" / "llama.cpp"); config["export"]["quant"] = "ALL"; config_path = tmp_root / "release_smoke.yaml"; config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8"); from pipeline.orchestrator import Pipeline; smoke_pipeline = Pipeline(str(config_path), resume=False); _write_local_smoke_input(scratch, pipeline_config_sha256=_sha256(config_path), run_id=smoke_pipeline.cfg["_run_id"], config_identities=smoke_pipeline._config_identities); _write_smoke_source_manifest(tmp_root, smoke_pipeline.cfg["_run_id"], smoke_pipeline._source_definition_paths)
        try: _validate_source_manifest(tmp_root / "source_manifest.json")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc: print(f"Invalid smoke source manifest: {exc}"); return 2
        if run([sys.executable, "run_pipeline.py", "--config", str(config_path), "--no-resume"]): return 2
        manifest_path = output / "gguf" / "export_manifest.json"
        if not manifest_path.is_file():
            print(f"Missing export manifest: {manifest_path}")
            return 2
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifacts = manifest.get("artifacts") or {}
            required_quants = {"F16", "Q4_K_M", "Q5_K_M", "Q8_0"}
            if set(artifacts) != required_quants:
                print(f"Export did not produce the required quantizations: {sorted(artifacts)}")
                return 2
            for quant, record in artifacts.items():
                final_gguf = Path(record["artifact"]["path"])
                artifact_manifest = Path(record["manifest"])
                if not final_gguf.is_file() or final_gguf.stat().st_size <= 0:
                    print(f"Missing final GGUF artifact for {quant}: {final_gguf}")
                    return 2
                if _sha256(final_gguf) != record["artifact"]["sha256"]:
                    print(f"GGUF hash mismatch for {quant}: {final_gguf}")
                    return 2
                if not artifact_manifest.is_file():
                    print(f"Missing per-export manifest for {quant}: {artifact_manifest}")
                    return 2
                per_export = json.loads(artifact_manifest.read_text(encoding="utf-8"))
                required = {"checkpoint_sha256", "model_config", "export_config", "exporter_version", "timestamp", "lineage", "artifact"}
                if not required <= set(per_export):
                    print(f"Export manifest is incomplete for {quant}: {artifact_manifest}")
                    return 2
                if per_export["artifact"].get("sha256") != _sha256(final_gguf):
                    print(f"Per-export artifact hash mismatch for {quant}")
                    return 2
                for key in ("dataset_card", "model_card"):
                    card = Path(manifest[key])
                    if not card.is_file() or card.stat().st_size <= 0:
                        print(f"Missing export card: {key}: {card}")
                        return 2
                    if manifest.get(f"{key}_sha256") != _sha256(card):
                        print(f"Export card hash mismatch: {key}: {card}")
                        return 2
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"Invalid export manifest: {exc}")
            return 2
        for quant, record in artifacts.items():
            artifact_manifest = Path(record["manifest"])
            final_gguf = Path(record["artifact"]["path"])
            model_cfg = manifest.get("model_config") or {}
            cmd = [
                sys.executable, "scripts/verify_gguf.py",
                "--model", str(final_gguf),
                "--llamacpp-dir", str(ROOT / "third_party" / "llama.cpp"),
                "--manifest", str(artifact_manifest),
                "--context-length", str(int(model_cfg.get("seq_len", 0))),
                "--bos-token-id", "2",
                "--eos-token-id", "3",
                "--pad-token-id", "0",
            ]
            if run(cmd):
                print(f"GGUF inference verification failed for {quant}")
                return 2
            try:
                result = json.loads(artifact_manifest.read_text(encoding="utf-8")).get("inference_validation", {})
                if result.get("status") != "passed" or not result.get("generated_output"):
                    print(f"Export manifest does not contain a passing inference validation result for {quant}")
                    return 2
            except (OSError, ValueError, TypeError) as exc:
                print(f"Unable to read validated export manifest for {quant}: {exc}")
                return 2
        if verify_ollama:
            for quant, record in artifacts.items():
                final_gguf = Path(record["artifact"]["path"])
                modelfile = Path(record["modelfile"])
                model_name = f"model-lab-rc-{quant.lower()}"
                if run([
                    sys.executable, "scripts/verify_ollama.py",
                    "--model", str(final_gguf),
                    "--modelfile", str(modelfile),
                    "--model-name", model_name,
                ]):
                    print(f"Ollama deployment verification failed for {quant}")
                    return 2
    return 0


def _report_check(name: str, status: str, detail: str = "") -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _write_release_report(*, static_failures: list[str], native_requested: bool, native_rc: int) -> int:
    """Write one machine-readable RC report. UNKNOWN is never silently promoted to PASS."""
    evidence = NATIVE_EVIDENCE
    checks: list[dict[str, str]] = []

    def add(name: str, ok: bool | None, detail: str = "") -> None:
        checks.append(_report_check(name, "PASS" if ok is True else "FAIL" if ok is False else "UNKNOWN", detail))

    add("tests", "pytest" not in static_failures, "compile/lint/pytest gate")
    add("configs", "doctor-required" not in static_failures, "canonical configuration and doctor")
    for name in ("provenance", "lineage", "dataset", "source_retrieval", "checkpoint", "best_checkpoint",
                 "reproducibility", "hardware", "auto_sizing", "eta", "evaluation", "sqlite", "export", "inference"):
        value = evidence.get(name)
        add(name, bool(value) if value is not None else None, "native release evidence" if value is not None else "not executed")
    add("ui_backend_connectivity", bool(evidence.get("ui_backend_connectivity")) if "ui_backend_connectivity" in evidence else None,
        "localhost FastAPI probe" if "ui_backend_connectivity" in evidence else "run with --ui-probe")
    add("clean_clone", bool(evidence.get("clean_clone")) if "clean_clone" in evidence else None,
        "temporary clone acceptance path" if "clean_clone" in evidence else "run with --clean-clone")
    add("documentation", (ROOT / "README.md").is_file() and (ROOT / "docs" / "development" / "START_HERE.md").is_file(), "release docs present")
    secret_value = evidence.get("secrets")
    add("secrets", bool(secret_value) if secret_value is not None else None, "security gate")
    git_status = _git_state(ROOT)
    add("git_state", git_status["commit"] is not None and not git_status["dirty"], json.dumps(git_status, sort_keys=True))
    package_artifacts = sorted((ROOT / "dist").glob("*"))
    release_artifacts_ok = bool(evidence.get("export") and evidence.get("inference")) and all(p.is_file() and p.stat().st_size > 0 for p in package_artifacts)
    add("release_artifacts", release_artifacts_ok if native_requested else None,
        f"native export/inference plus {len(package_artifacts)} package artifact(s)")

    required = checks
    gate_pass = native_requested and native_rc == 0 and not static_failures and all(c["status"] == "PASS" for c in required)
    report = {
        "schema": 1,
        "release": "ML-FRAMEWORK RC",
        "status": "PASS" if gate_pass else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": git_status,
        "python": sys.version,
        "platform": platform.platform(),
        "checks": checks,
        "native_requested": native_requested,
        "native_return_code": native_rc,
        "failures": list(static_failures),
        "native_evidence": evidence,
    }
    out = ROOT / "release-evidence"
    out.mkdir(exist_ok=True)
    path = out / "release_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Release report: {path}")
    return 0 if gate_pass else 2


def _ui_probe() -> bool:
    try:
        from fastapi.testclient import TestClient
        from command_center.web import app
        with TestClient(app) as client:
            response = client.get("/api/system")
            return response.status_code == 200 and response.json().get("version") == "1.3.0"
    except Exception as exc:
        print(f"UI/backend probe failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Model Lab production verification gate."); parser.add_argument("--bootstrap-native", action="store_true", help="bootstrap pinned llama.cpp and validate native GGUF inference"); parser.add_argument("--skip-tests", action="store_true", help="not allowed for production verification"); parser.add_argument("--verify-ollama", action="store_true", help="also verify every exported GGUF through Ollama")
    parser.add_argument("--ui-probe", action="store_true", help="probe the localhost FastAPI backend")
    parser.add_argument("--clean-clone", action="store_true", help="exercise the documented clone/install/doctor/smoke path in a temporary clone")
    args = parser.parse_args()
    if args.skip_tests: print("RELEASE VERIFICATION FAILED: --skip-tests is not allowed for a production verification."); return 2
    failures: list[str] = []; compile_targets = ["pipeline", "command_center", "scripts", "ui", "run_pipeline.py", "run_command_center.py", "launch.py"]
    if run([sys.executable, "-m", "compileall", "-q", *compile_targets]): failures.append("compileall")
    if run(["ruff", "check", "--select", "F", *LINT_TARGETS]): failures.append("ruff")
    evidence = ROOT / "release-evidence"; evidence.mkdir(exist_ok=True)
    if run([sys.executable, "-m", "pytest", "-q", "--cov-report=json:release-evidence/coverage.json"]): failures.append("pytest")
    if run([sys.executable, "run_pipeline.py", "--doctor"]): failures.append("doctor-required")
    if failures:
        _write_release_report(static_failures=failures, native_requested=args.bootstrap_native, native_rc=2)
        print("RELEASE VERIFICATION FAILED:", ", ".join(failures))
        print("Platform:", platform.platform())
        return 2
    if args.ui_probe:
        NATIVE_EVIDENCE["ui_backend_connectivity"] = _ui_probe()
    security_rc = run([sys.executable, "scripts/security_gate.py"])
    NATIVE_EVIDENCE["secrets"] = security_rc == 0
    if security_rc:
        failures.append("security")
    if not args.bootstrap_native:
        _write_release_report(static_failures=failures, native_requested=False, native_rc=0)
        print("STATIC VERIFICATION PASSED: syntax, lint, coverage, tests, and required environment checks are green.")
        print("Native artifact verification was not run. A production release requires --bootstrap-native.")
        return 0
    if run([sys.executable, "scripts/reconcile_environment.py", "--project-root", str(ROOT), "--ensure-llamacpp"]):
        _write_release_report(static_failures=["llama.cpp-bootstrap"], native_requested=True, native_rc=2)
        print("RELEASE VERIFICATION FAILED: llama.cpp-bootstrap")
        print("Platform:", platform.platform())
        return 2
    print("native export prerequisites are green")
    native_rc = _native_smoke(verify_ollama=args.verify_ollama)
    if native_rc:
        _write_release_report(static_failures=["native export/inference"], native_requested=True, native_rc=native_rc)
        print("RELEASE VERIFICATION FAILED: native export/inference")
        print("Platform:", platform.platform())
        return 2
    if args.clean_clone:
        with tempfile.TemporaryDirectory(prefix="model-lab-clean-clone-") as clone_dir:
            clone = Path(clone_dir) / "ML-Framework"
            remote = _git(ROOT, "config", "--get", "remote.origin.url") or "https://github.com/psfr4590-afk/ML-Framework.git"
            clone_rc = run(["git", "clone", "--depth", "1", remote, str(clone)])
            if clone_rc:
                NATIVE_EVIDENCE["clean_clone"] = False
            else:
                install = subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(clone), "--no-deps"], cwd=clone, check=False)
                doctor = subprocess.run([sys.executable, str(clone / "bootstrap.py"), "--doctor"], cwd=clone, check=False)
                smoke = subprocess.run([sys.executable, str(clone / "mlframework.py"), "smoke"], cwd=clone, check=False) if doctor.returncode == 0 else None
                NATIVE_EVIDENCE["clean_clone"] = install.returncode == 0 and doctor.returncode == 0 and smoke is not None and smoke.returncode == 0
    if args.ui_probe and not NATIVE_EVIDENCE.get("ui_backend_connectivity"):
        failures.append("ui-backend")
    NATIVE_EVIDENCE["export"] = True
    NATIVE_EVIDENCE["inference"] = True
    rc = _write_release_report(static_failures=failures, native_requested=True, native_rc=native_rc)
    if rc:
        print("RELEASE VERIFICATION FAILED: RC report contains a required non-PASS check.")
        return 2
    print("RELEASE VERIFICATION PASSED: ML-FRAMEWORK RC report is green.")
    return 0


if __name__ == "__main__": raise SystemExit(main())