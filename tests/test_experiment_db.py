from __future__ import annotations

import json
import sqlite3

from pipeline.experiment_db import ExperimentDB


def _manifest() -> dict:
    return {
        "schema": 1,
        "run_id": "run_test_001",
        "experiment_id": "exp:test",
        "dataset_id": "dataset_test",
        "timestamps": {"started": "2026-10-06T10:00:00+00:00", "updated": "2026-10-06T10:01:00+00:00", "ended": "2026-10-06T10:02:00+00:00"},
        "git": {"commit": "abc123", "branch": "test", "dirty": False},
        "hardware": {"host": {"platform": "test", "cpu_name": "CPU", "cpu_threads": 12, "total_ram_gb": 8.0}, "torch": {"version": "2.0", "device_count": 0}},
        "configuration": {"train_config_sha256": "cfg123"},
        "dataset_identity": {"dataset_id": "dataset_test", "requested_group": "ai_ml"},
        "stages": {
            "crawl": {
                "status": "PASS", "start": "2026-10-06T10:00:00+00:00", "end": "2026-10-06T10:00:10+00:00",
                "duration_seconds": 10.0, "metrics": {"document_count": 4, "token_count": 100},
            }
        },
        "artifacts": [{"stage": "crawl", "path": "scratch/01_crawled.jsonl", "sha256": "artifact123"}],
        "warnings": [],
        "errors": [],
        "final_status": "PASS",
    }


def test_database_persists_and_reopens(tmp_path):
    path = tmp_path / "output" / "experiment.db"
    db = ExperimentDB(path)
    db.sync_manifest(_manifest())
    db.close()

    reopened = ExperimentDB(path)
    run = reopened.get_run("run_test_001")
    assert run is not None
    assert run["status"] == "PASS"
    assert reopened.search_runs(status="PASS")[0]["id"] == "run_test_001"
    lineage = reopened.lineage("run_test_001")
    assert lineage["dataset"][0]["id"] == "dataset_test"
    assert lineage["stages"][0]["stage_name"] == "crawl"
    assert lineage["artifacts"][0]["sha256"] == "artifact123"
    reopened.close()


def test_schema_retains_raw_evidence_relationships(tmp_path):
    path = tmp_path / "experiment.db"
    db = ExperimentDB(path)
    db.sync_manifest(_manifest())
    tables = {
        row[0]
        for row in sqlite3.connect(path).execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"experiments", "runs", "datasets", "sources", "stages", "artifacts", "checkpoints", "metrics", "evaluations",
            "hardware", "configs", "warnings", "errors", "runtime_estimates"} <= tables
    assert json.loads(db.conn.execute("SELECT snapshot_json FROM hardware").fetchone()[0])["host"]["platform"] == "test"
    db.close()


def test_compare_runs_returns_structured_evidence(tmp_path):
    db = ExperimentDB(tmp_path / "experiment.db")
    first = _manifest()
    second = _manifest()
    second["run_id"] = "run_test_002"
    second["git"]["commit"] = "def456"
    db.sync_manifest(first)
    db.sync_manifest(second)
    comparison = db.compare_runs("run_test_001", "run_test_002")
    assert {row["id"] for row in comparison["runs"]} == {"run_test_001", "run_test_002"}
    db.close()
