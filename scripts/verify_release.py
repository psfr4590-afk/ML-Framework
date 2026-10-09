#!/usr/bin/env python3
"""Deterministic production verification for Model Lab.

The native gate runs a bounded, network-free release fixture before native inference.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import platform
import subprocess
import sys
import sqlite3
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

NATIVE_EVIDENCE: dict[str, object] = {}

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import yaml  # noqa: E402
from pipeline.integrity import write_manifest  # noqa: E402
from pipeline.provenance import stable_hash  # noqa: E402
from pipeline.run_tracking import _git, _git_state  # noqa: E402
from pipeline.types import Document  # noqa: E402

LINT_TARGETS = ["command_center", "pipeline", "tests", "scripts", "run_pipeline.py", "run_command_center.py", "launch.py", "bootstrap.py"]
RELEASE_SMOKE_SOURCES = (("local-technical", "systems architecture, compilers, operating systems, networking, storage, and distributed computing"),("local-scientific", "physics, chemistry, biology, astronomy, mathematics, statistics, and experimental methods"),("local-engineering", "mechanical, electrical, civil, software, control systems, reliability, and manufacturing engineering"),("local-humanities", "history, literature, linguistics, philosophy, archaeology, anthropology, and cultural studies"),("local-business", "accounting, finance, economics, operations, logistics, management, markets, and entrepreneurship"),("local-geography", "cartography, climate, geology, ecology, oceans, weather, agriculture, and geographic information"),("local-medicine", "anatomy, physiology, epidemiology, diagnostics, pharmacology, public health, and clinical research"),("local-creative", "music, visual design, architecture, photography, theater, film, animation, and digital media"))


def run(cmd: list[str]) -> int:
    print("$", " ".join(map(str, cmd))); return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


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
    if config_identities:
        provenance["config_identities"] = dict(config_identities)
        provenance["identity_bundle_sha256"] = stable_hash(config_identities)
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
    source = ROOT / "config" / "pipeline_config.smoke.yaml"; config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}; config["stages"] = {"crawl": False, "clean": False, "dedup": False, "weight": False, "tokenize": True, "shard": True, "train": True, "export": True}
    with tempfile.TemporaryDirectory(prefix="model-lab-release-") as tmp:
        tmp_root = Path(tmp); output = tmp_root / "output"; scratch = tmp_root / "scratch"; config.setdefault("pipeline", {})["output_dir"] = str(output); config["pipeline"]["scratch_dir"] = str(scratch); config["pipeline"]["resume"] = False; config.setdefault("export", {})["llamacpp_dir"] = str(ROOT / "third_party" / "llama.cpp"); config["export"]["quant"] = "ALL"; config_path = tmp_root / "release_smoke.yaml"; config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8"); from pipeline.orchestrator import Pipeline
        smoke_pipeline = Pipeline(str(config_path), resume=False)
        run_id = smoke_pipeline.cfg["_run_id"]
        try:
            _write_local_smoke_input(
                scratch,
                pipeline_config_sha256=_sha256(config_path),
                run_id=smoke_pipeline.cfg["_run_id"],
                config_identities=smoke_pipeline._config_identities,
            )
            _write_smoke_source_manifest(
                tmp_root,
                smoke_pipeline.cfg["_run_id"],
                smoke_pipeline._source_definition_paths,
            )
        finally:
            smoke_pipeline.close()
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
        run_manifest_path = output / "runs" / run_id / "run_manifest.json"
        NATIVE_EVIDENCE["export"] = True
        NATIVE_EVIDENCE["inference"] = True
        _harvest_native_evidence(
            output=output,
            run_id=run_id,
            run_manifest_path=run_manifest_path,
        )
    return 0


def _auto_sizing_evidence(train_metrics: object) -> bool | None:
    """Read auto-sizing evidence from persisted train metrics."""
    if not isinstance(train_metrics, dict):
        return None

    # Current run manifests persist these fields directly under metrics.train.
    effective = train_metrics.get("effective_configuration")
    if isinstance(effective, dict):
        value = effective.get("auto_size")
        if isinstance(value, bool):
            return value

    # Also support trainer metadata wrappers used by other artifact formats.
    training_metadata = train_metrics.get("training_metadata")
    if isinstance(training_metadata, dict):
        effective = training_metadata.get("effective_configuration")
        if isinstance(effective, dict):
            value = effective.get("auto_size")
            if isinstance(value, bool):
                return value

        value = training_metadata.get("auto_size")
        if isinstance(value, bool):
            return value

    # Backward compatibility with older run manifests.
    value = train_metrics.get("auto_size")
    return value if isinstance(value, bool) else None


def _validate_best_checkpoint_metadata(meta: dict) -> None:
    """Enforce the checkpoint manifest contract used by best_checkpoint()."""
    if not isinstance(meta, dict):
        raise RuntimeError("best checkpoint metadata is invalid")
    if meta.get("checkpoint_kind") != "best":
        raise RuntimeError("checkpoint manifest is not marked as best")
    step = meta.get("step")
    best_step = meta.get("best_step")
    if isinstance(step, bool) or not isinstance(step, int) or step < 0:
        raise RuntimeError("best checkpoint step metadata is invalid")
    if isinstance(best_step, bool) or not isinstance(best_step, int) or best_step < 0:
        raise RuntimeError("best checkpoint best_step metadata is invalid")
    loss = meta.get("best_val_loss")
    if (
        isinstance(loss, bool)
        or not isinstance(loss, (int, float))
        or not math.isfinite(loss)
    ):
        raise RuntimeError("best checkpoint best_val_loss must be finite")


def _validate_checkpoint_identity_chain(expected: dict, actual: dict) -> None:
    """Require stable cross-stage SHA-256 identities and exact agreement."""
    required = (
        "dataset_config_sha256",
        "tokenizer_config_sha256",
        "shard_config_sha256",
        "export_config_sha256",
        "source_definition_sha256",
    )

    if not isinstance(expected, dict) or not isinstance(actual, dict):
        raise RuntimeError("configuration identity chain is missing")

    for key in required:
        expected_hash = expected.get(key)
        actual_hash = actual.get(key)
        for label, value in (("run configuration", expected_hash),
                             ("checkpoint provenance", actual_hash)):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in value)
            ):
                raise RuntimeError(f"invalid or missing {key} in {label}")
        if actual_hash.lower() != expected_hash.lower():
            raise RuntimeError(f"checkpoint provenance identity mismatch: {key}")


def _harvest_native_evidence(
    *,
    output: Path,
    run_id: str,
    run_manifest_path: Path,
) -> None:
    """Validate and retain durable evidence from the completed native smoke run."""
    evidence: dict[str, object] = {}

    try:
        if not run_manifest_path.is_file():
            raise RuntimeError(f"missing run manifest: {run_manifest_path}")

        manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_id") != run_id:
            raise RuntimeError(
                f"run id mismatch: expected={run_id} actual={manifest.get('run_id')}"
            )
        if manifest.get("final_status") != "PASS":
            raise RuntimeError(
                f"run manifest final_status={manifest.get('final_status')!r}"
            )
        if manifest.get("errors"):
            raise RuntimeError(f"run manifest contains errors: {manifest['errors']}")
        if manifest.get("degraded_stages"):
            raise RuntimeError(
                f"run manifest contains degraded stages: {manifest['degraded_stages']}"
            )

        identities = manifest.get("configuration")
        if not isinstance(identities, dict) or not identities:
            raise RuntimeError("run manifest has no config identities")

        dataset_report = run_manifest_path.parent / "dataset_report.json"
        if not dataset_report.is_file():
            raise RuntimeError(f"missing dataset report: {dataset_report}")

        dataset_payload = json.loads(
            dataset_report.read_text(encoding="utf-8")
        )
        dataset_sha = _sha256(dataset_report)
        recorded_dataset = manifest.get("dataset_report") or {}
        if recorded_dataset.get("sha256") != dataset_sha:
            raise RuntimeError(
                "dataset report SHA-256 does not match run manifest"
            )

        stages = manifest.get("stages") or {}
        required_stages = ("tokenize", "shard", "train", "export")
        if any((stages.get(name) or {}).get("status") != "PASS"
               for name in required_stages):
            raise RuntimeError(
                "required native stages are not all PASS"
            )

        skipped_upstream = ("crawl", "clean", "dedup", "weight")
        source_retrieval_exercised = any(
            (stages.get(name) or {}).get("status") == "PASS"
            for name in skipped_upstream
        )

        # Dataset evidence is intentionally bounded to the local native smoke fixture.
        evidence["dataset"] = bool(
            dataset_payload
            and manifest.get("dataset_identity")
            and (manifest.get("metrics") or {})
        )

        # The native smoke intentionally bypasses external retrieval.
        evidence["source_retrieval"] = (
            True if source_retrieval_exercised else None
        )

        train_metrics = (
            manifest.get("metrics", {}).get("train")
            or stages.get("train", {}).get("metrics")
            or {}
        )

        preflight = train_metrics.get("preflight")
        if isinstance(preflight, dict):
            viable = preflight.get("viable")
            evidence["eta"] = viable is True
            evidence["hardware"] = bool(
                manifest.get("hardware")
                or preflight.get("hardware")
            )
        else:
            evidence["eta"] = None
            evidence["hardware"] = bool(manifest.get("hardware"))

        evidence["auto_sizing"] = _auto_sizing_evidence(train_metrics)

        evidence["evaluation"] = bool(
            train_metrics.get("val_loss") is not None
            and train_metrics.get("best_val_loss") is not None
        )

        evidence["reproducibility"] = bool(
            train_metrics.get("seed") is not None
            and train_metrics.get("random_state_sha256")
        )

        # Checkpoint evidence.
        checkpoint_dir = output / "checkpoints"
        final_ckpt = checkpoint_dir / "ckpt_final.pt"
        best_ckpt = checkpoint_dir / "ckpt_best.pt"

        if not final_ckpt.is_file() or final_ckpt.stat().st_size <= 0:
            raise RuntimeError("final checkpoint missing or empty")
        if not best_ckpt.is_file() or best_ckpt.stat().st_size <= 0:
            raise RuntimeError("best checkpoint missing or empty")

        from pipeline.trainer.train import checkpoint_metadata

        final_meta = checkpoint_metadata(final_ckpt)
        best_meta = checkpoint_metadata(best_ckpt)

        if not isinstance(final_meta, dict) or not isinstance(best_meta, dict):
            raise RuntimeError("checkpoint metadata is invalid")

        if final_meta.get("step") is None or best_meta.get("step") is None:
            raise RuntimeError("checkpoint step metadata missing")

        _validate_best_checkpoint_metadata(best_meta)
        evidence["checkpoint"] = True
        evidence["best_checkpoint"] = True

        # Provenance: checkpoint metadata must contain the immutable identity chain.
        provenance = (
            final_meta.get("provenance")
            or final_meta.get("training_metadata", {}).get("provenance")
        )

        if not isinstance(provenance, dict):
            raise RuntimeError("final checkpoint provenance is missing")

        checkpoint_identities = provenance.get("config_identities")
        if not isinstance(checkpoint_identities, dict):
            raise RuntimeError("checkpoint config identities are missing")

        _validate_checkpoint_identity_chain(identities, checkpoint_identities)

        evidence["provenance"] = True

        parent_ids = provenance.get("parent_artifact_ids")
        evidence["lineage"] = bool(
            provenance.get("run_id") == run_id
            and isinstance(parent_ids, list)
            and parent_ids
            and provenance.get("dataset_artifact_id")
            and provenance.get("tokenizer_artifact_id")
        )

        # SQLite must contain the same run and durable tracking evidence.
        db_path = output / "experiment.db"
        if not db_path.is_file():
            raise RuntimeError(f"missing experiment database: {db_path}")

        with closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT id, status, git_sha, git_branch FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()

            if row is None:
                raise RuntimeError(f"run {run_id} missing from experiment.db")

            if row["status"] != "PASS":
                raise RuntimeError(
                    f"SQLite run status is {row['status']!r}, expected PASS"
                )

            stage_count = conn.execute(
                "SELECT COUNT(*) FROM stages WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]

            checkpoint_count = conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]

            hardware_count = conn.execute(
                "SELECT COUNT(*) FROM hardware WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]

            evaluation_count = conn.execute(
                "SELECT COUNT(*) FROM evaluations WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]

            if stage_count < 4:
                raise RuntimeError("SQLite stage evidence is incomplete")
            if checkpoint_count < 2:
                raise RuntimeError("SQLite checkpoint evidence is incomplete")
            if hardware_count < 1:
                raise RuntimeError("SQLite hardware evidence is missing")
            if evaluation_count < 1:
                raise RuntimeError("SQLite evaluation evidence is missing")

        evidence["sqlite"] = True

        # Export/inference were already structurally validated by _native_smoke().
        evidence["export"] = True
        evidence["inference"] = True

    except Exception as exc:
        print(f"Native evidence validation failed: {exc}")
        validated_export = NATIVE_EVIDENCE.get("export") is True
        validated_inference = NATIVE_EVIDENCE.get("inference") is True
        NATIVE_EVIDENCE.clear()
        NATIVE_EVIDENCE["provenance"] = False
        NATIVE_EVIDENCE["lineage"] = False
        NATIVE_EVIDENCE["dataset"] = False
        NATIVE_EVIDENCE["checkpoint"] = False
        NATIVE_EVIDENCE["best_checkpoint"] = False
        NATIVE_EVIDENCE["reproducibility"] = False
        NATIVE_EVIDENCE["hardware"] = False
        NATIVE_EVIDENCE["eta"] = False
        NATIVE_EVIDENCE["evaluation"] = False
        NATIVE_EVIDENCE["sqlite"] = False
        NATIVE_EVIDENCE["export"] = validated_export
        NATIVE_EVIDENCE["inference"] = validated_inference
        return

    # Preserve validated native evidence before TemporaryDirectory removes the run.
    import shutil
    evidence_root = ROOT / "release-evidence" / "native-smoke" / run_id
    evidence_root.mkdir(parents=True, exist_ok=True)
    for source in (run_manifest_path, dataset_report, db_path):
        shutil.copy2(source, evidence_root / source.name)
    for source in output.rglob("*"):
        if source.is_file() and (
            source.suffix.lower() == ".json" and "manifest" in source.name.lower()
        ):
            destination = evidence_root / "artifacts" / source.relative_to(output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    NATIVE_EVIDENCE.update(evidence)


def _build_and_validate_wheel() -> tuple[bool, str]:
    """Build and validate a wheel in a disposable directory."""
    with tempfile.TemporaryDirectory(prefix="model-lab-wheel-") as tmp:
        wheel_dir = Path(tmp)
        result = subprocess.run(
            [
                sys.executable, "-m", "pip", "wheel", ".",
                "--no-deps", "--no-build-isolation",
                "--wheel-dir", str(wheel_dir),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "wheel build failed").strip()
            return False, detail[-2000:]

        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            return False, f"Expected exactly one wheel, found {len(wheels)}"

        wheel = wheels[0]
        try:
            with zipfile.ZipFile(wheel) as archive:
                corrupt = archive.testzip()
                if corrupt is not None:
                    return False, f"Corrupt wheel member: {corrupt}"

                names = set(archive.namelist())
                suffixes = (
                    ".dist-info/METADATA",
                    ".dist-info/WHEEL",
                    ".dist-info/RECORD",
                    ".dist-info/entry_points.txt",
                )
                paths = {}
                for suffix in suffixes:
                    matches = [name for name in names if name.endswith(suffix)]
                    if len(matches) != 1:
                        return False, (
                            f"Wheel must contain exactly one {suffix}; "
                            f"found {len(matches)}"
                        )
                    paths[suffix] = matches[0]

                metadata = Parser().parsestr(
                    archive.read(paths[".dist-info/METADATA"]).decode("utf-8")
                )
                project = tomllib.loads(
                    (ROOT / "pyproject.toml").read_text(encoding="utf-8")
                )["project"]
                normalize = lambda value: value.lower().replace("_", "-")

                if normalize(metadata.get("Name", "")) != normalize(project["name"]):
                    return False, "Wheel package name does not match pyproject.toml"
                if metadata.get("Version") != project["version"]:
                    return False, "Wheel version does not match pyproject.toml"

                required_modules = {
                    "run_pipeline.py",
                    "mlframework.py",
                    "run_command_center.py",
                    "launch.py",
                }
                missing = required_modules - names
                if missing:
                    return False, f"Missing wheel modules: {sorted(missing)}"

                parser = configparser.ConfigParser()
                parser.read_string(
                    archive.read(paths[".dist-info/entry_points.txt"]).decode("utf-8")
                )
                actual = (
                    dict(parser.items("console_scripts"))
                    if parser.has_section("console_scripts")
                    else {}
                )
                expected = {
                    "mlab": "run_pipeline:main",
                    "mlframework": "mlframework:main",
                    "mlab-command-center": "run_command_center:main",
                    "mlab-launch": "launch:main",
                }
                for name, target in expected.items():
                    if actual.get(name) != target:
                        return False, f"Missing or incorrect console entry point: {name}"

        except (
            OSError, ValueError, KeyError, zipfile.BadZipFile, configparser.Error
        ) as exc:
            return False, f"Wheel validation failed: {exc}"

        return True, f"Validated {wheel.name} ({wheel.stat().st_size} bytes)"


def _report_check(name: str, status: str, detail: str = "") -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _write_release_report(
    *,
    static_failures: list[str],
    native_requested: bool,
    native_rc: int,
    profile: str | None = None,
) -> int:
    """Write a verification report without confusing smoke evidence with RC certification."""
    profile = profile or ("rc" if native_requested else "static")
    if profile not in {"static", "native-smoke", "rc"}:
        raise ValueError(f"Unknown release verification profile: {profile}")

    evidence = NATIVE_EVIDENCE
    checks: list[dict[str, str]] = []

    def add(name: str, ok: bool | None, detail: str = "") -> None:
        status = "PASS" if ok is True else "FAIL" if ok is False else "UNKNOWN"
        checks.append(_report_check(name, status, detail))

    add("tests", "pytest" not in static_failures, "compile/lint/pytest gate")
    add("configs", "doctor-required" not in static_failures, "canonical configuration and doctor")

    native_checks = (
        "provenance", "lineage", "dataset", "source_retrieval", "checkpoint",
        "best_checkpoint", "reproducibility", "hardware", "auto_sizing", "eta",
        "evaluation", "sqlite", "export", "inference",
    )
    for name in native_checks:
        value = evidence.get(name)
        add(
            name,
            bool(value) if value is not None else None,
            "native release evidence" if value is not None else "not executed",
        )

    add(
        "ui_backend_connectivity",
        bool(evidence["ui_backend_connectivity"])
        if "ui_backend_connectivity" in evidence else None,
        "localhost FastAPI probe"
        if "ui_backend_connectivity" in evidence else "run with --ui-probe",
    )
    add(
        "clean_clone",
        bool(evidence["clean_clone"]) if "clean_clone" in evidence else None,
        "temporary clone acceptance path"
        if "clean_clone" in evidence else "run with --clean-clone",
    )
    add(
        "documentation",
        (ROOT / "README.md").is_file()
        and (ROOT / "docs" / "development" / "START_HERE.md").is_file(),
        "release docs present",
    )
    secret_value = evidence.get("secrets")
    add(
        "secrets",
        bool(secret_value) if secret_value is not None else None,
        "security gate",
    )

    git_status = _git_state(ROOT)
    add(
        "git_state",
        git_status["commit"] is not None and not git_status["dirty"],
        json.dumps(git_status, sort_keys=True),
    )

    package_value = evidence.get("package")
    package_status = (
        package_value if package_value is True or package_value is False else None
    )
    add(
        "package",
        package_status,
        str(evidence.get("package_detail", "package build not executed")),
    )

    native_artifacts_ok = (
        evidence.get("export") is True and evidence.get("inference") is True
    )
    add(
        "release_artifacts",
        native_artifacts_ok if native_requested else None,
        "native GGUF export and inference evidence",
    )

    # Static verification, native smoke, and full RC certification have
    # deliberately different acceptance criteria.
    required_by_profile = {
        "static": {"tests", "configs", "documentation", "secrets"},
        "native-smoke": {
            "tests", "configs", "provenance", "lineage", "dataset",
            "checkpoint", "best_checkpoint", "reproducibility", "hardware",
            "eta", "evaluation", "sqlite", "export", "inference",
            "documentation", "secrets", "release_artifacts",
        },
        "rc": {check["name"] for check in checks},
    }
    required_names = set(required_by_profile[profile])
    if profile == "native-smoke":
        if "ui_backend_connectivity" in evidence:
            required_names.add("ui_backend_connectivity")
        if "clean_clone" in evidence:
            required_names.add("clean_clone")

    required = [check for check in checks if check["name"] in required_names]
    blockers = [
        f"{check['name']}: {check['status']}"
        for check in required
        if check["status"] != "PASS"
    ]

    gate_pass = (
        not static_failures
        and all(check["status"] == "PASS" for check in required)
        and (
            profile == "static"
            or (native_requested and native_rc == 0)
        )
    )

    report = {
        "schema": 1,
        "release": {
            "static": "ML-FRAMEWORK STATIC VERIFICATION",
            "native-smoke": "ML-FRAMEWORK NATIVE SMOKE",
            "rc": "ML-FRAMEWORK RC",
        }[profile],
        "profile": profile,
        "status": "PASS" if gate_pass else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": git_status,
        "python": sys.version,
        "platform": platform.platform(),
        "checks": checks,
        "required_checks": sorted(required_names),
        "native_requested": native_requested,
        "native_return_code": native_rc,
        "failures": list(dict.fromkeys([*static_failures, *blockers])),
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
            return response.status_code == 200 and response.json().get("version") == _project_version()
    except Exception as exc:
        print(f"UI/backend probe failed: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Model Lab production verification gate."); parser.add_argument("--bootstrap-native", action="store_true", help="bootstrap pinned llama.cpp and validate native GGUF inference"); parser.add_argument("--skip-tests", action="store_true", help="not allowed for production verification"); parser.add_argument("--verify-ollama", action="store_true", help="also verify every exported GGUF through Ollama")
    parser.add_argument("--ui-probe", action="store_true", help="probe the localhost FastAPI backend")
    parser.add_argument("--clean-clone", action="store_true", help="exercise the documented clone/install/doctor/smoke path in a temporary clone")
    parser.add_argument(
        "--profile",
        choices=("static", "native-smoke", "rc"),
        default=None,
        help="verification profile; rc requires --bootstrap-native, --ui-probe, and --clean-clone",
    )
    args = parser.parse_args()
    profile = args.profile or (
        "native-smoke" if args.bootstrap_native else "static"
    )
    if profile in {"native-smoke", "rc"} and not args.bootstrap_native:
        parser.error(f"--profile {profile} requires --bootstrap-native")
    if profile == "static" and args.bootstrap_native:
        parser.error("--profile static cannot be combined with --bootstrap-native")
    if profile == "rc" and not args.ui_probe:
        parser.error("--profile rc requires --ui-probe")
    if profile == "rc" and not args.clean_clone:
        parser.error("--profile rc requires --clean-clone")
    if args.skip_tests: print("RELEASE VERIFICATION FAILED: --skip-tests is not allowed for a production verification."); return 2
    failures: list[str] = []; compile_targets = ["pipeline", "command_center", "scripts", "ui", "run_pipeline.py", "run_command_center.py", "launch.py"]
    if run([sys.executable, "-m", "compileall", "-q", *compile_targets]): failures.append("compileall")
    if run(["ruff", "check", "--select", "F", *LINT_TARGETS]): failures.append("ruff")
    evidence = ROOT / "release-evidence"; evidence.mkdir(exist_ok=True)
    if run([sys.executable, "-m", "pytest", "-q", "--cov-report=json:release-evidence/coverage.json"]): failures.append("pytest")
    if run([sys.executable, "run_pipeline.py", "--doctor"]): failures.append("doctor-required")
    if failures:
        _write_release_report(static_failures=failures, native_requested=args.bootstrap_native, native_rc=2, profile=profile)
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
        static_rc = _write_release_report(
            static_failures=failures,
            native_requested=False,
            native_rc=0,
            profile="static",
        )
        if static_rc:
            print("STATIC VERIFICATION FAILED: report contains a required non-PASS check.")
            return 2
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
            expected_commit = _git(ROOT, "rev-parse", "HEAD")
            clone_rc = run(["git", "clone", "--depth", "1", remote, str(clone)])
            if clone_rc or not expected_commit:
                NATIVE_EVIDENCE["clean_clone"] = False
            else:
                fetch = subprocess.run(["git", "fetch", "--depth", "1", "origin", expected_commit], cwd=clone, check=False)
                checkout = subprocess.run(["git", "checkout", "--detach", expected_commit], cwd=clone, check=False) if fetch.returncode == 0 else None
                checked_out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone, check=False, capture_output=True, text=True) if checkout and checkout.returncode == 0 else None
                exact_source = bool(checked_out and checked_out.returncode == 0 and checked_out.stdout.strip() == expected_commit)
                venv_dir = clone / ".release-venv"
                venv_python = venv_dir / "bin" / "python"
                if sys.platform == "win32":
                    venv_python = venv_dir / "Scripts" / "python.exe"
                create_venv = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], cwd=clone, check=False) if exact_source else None
                install_torch = subprocess.run([str(venv_python), "-m", "pip", "install", "-r", "requirements-torch.txt", "--index-url", "https://download.pytorch.org/whl/cpu"], cwd=clone, check=False) if create_venv and create_venv.returncode == 0 else None
                install = subprocess.run([str(venv_python), "-m", "pip", "install", str(clone)], cwd=clone, check=False) if install_torch and install_torch.returncode == 0 else None
                doctor = subprocess.run([str(venv_python), str(clone / "bootstrap.py"), "--doctor"], cwd=clone, check=False) if install and install.returncode == 0 else None
                smoke = subprocess.run([str(venv_python), str(clone / "mlframework.py"), "smoke"], cwd=clone, check=False) if doctor and doctor.returncode == 0 else None
                NATIVE_EVIDENCE["clean_clone"] = bool(exact_source and create_venv and create_venv.returncode == 0 and install_torch and install_torch.returncode == 0 and install and install.returncode == 0 and doctor and doctor.returncode == 0 and smoke and smoke.returncode == 0)
        if not NATIVE_EVIDENCE.get("clean_clone"):
            failures.append("clean-clone")
    if args.ui_probe and not NATIVE_EVIDENCE.get("ui_backend_connectivity"):
        failures.append("ui-backend")
    if profile == "rc":
        package_ok, package_detail = _build_and_validate_wheel()
        NATIVE_EVIDENCE["package"] = package_ok
        NATIVE_EVIDENCE["package_detail"] = package_detail

    rc = _write_release_report(
        static_failures=failures,
        native_requested=True,
        native_rc=native_rc,
        profile=profile,
    )
    if rc:
        print(f"RELEASE VERIFICATION FAILED: {profile} report contains a required non-PASS check.")
        return 2
    if profile == "rc":
        print("RC VERIFICATION PASSED: all required RC checks are green.")
    else:
        print("NATIVE SMOKE VERIFICATION PASSED: native-smoke report is green.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
