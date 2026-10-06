"""SQLite source of truth for durable experiment and run observability.

The database is structured operational state. Raw JSON/log artifacts remain the
forensic evidence and are never deleted or replaced by this store.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(id),
    dataset_id TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    git_sha TEXT,
    git_branch TEXT,
    git_dirty INTEGER,
    entrypoint TEXT,
    parent_run_id TEXT
);
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    dataset_group TEXT,
    manifest_sha256 TEXT,
    document_count INTEGER,
    token_count INTEGER,
    train_tokens INTEGER,
    validation_tokens INTEGER
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT REFERENCES datasets(id),
    kind TEXT NOT NULL,
    identifier TEXT NOT NULL,
    revision TEXT,
    license TEXT,
    raw_source_sha256 TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS source_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),
    requests INTEGER,
    successes INTEGER,
    failures INTEGER,
    http_2xx INTEGER,
    http_4xx INTEGER,
    http_5xx INTEGER,
    documents INTEGER,
    retries INTEGER,
    duration_seconds REAL
);
CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_seconds REAL,
    records_in INTEGER,
    records_out INTEGER,
    tokens INTEGER,
    throughput REAL,
    input_artifact_id TEXT,
    output_artifact_id TEXT,
    UNIQUE(run_id, stage_name)
);
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    stage_name TEXT,
    path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    created_at TEXT,
    parent_artifact_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    artifact_id TEXT,
    step INTEGER,
    val_loss REAL,
    best_val_loss REAL,
    is_best INTEGER NOT NULL DEFAULT 0,
    is_final INTEGER NOT NULL DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    step INTEGER,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    metric_unit TEXT,
    recorded_at TEXT
);
CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    score REAL,
    step INTEGER,
    artifact_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hardware (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    platform TEXT,
    cpu_name TEXT,
    cpu_threads INTEGER,
    ram_gb REAL,
    gpu_name TEXT,
    gpu_count INTEGER,
    gpu_memory_gb REAL,
    cuda_version TEXT,
    driver_version TEXT,
    pytorch_version TEXT,
    disk_free_gb REAL,
    disk_total_gb REAL,
    snapshot_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    config_type TEXT NOT NULL,
    sha256 TEXT,
    path TEXT,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(run_id, config_type)
);
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    stage_id INTEGER,
    code TEXT,
    message TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    stage_id INTEGER,
    code TEXT,
    message TEXT NOT NULL,
    exception_type TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS runtime_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    estimate_type TEXT NOT NULL,
    estimated_seconds REAL,
    actual_seconds REAL,
    tokens_per_second REAL,
    steps_per_second REAL,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_git_sha ON runs(git_sha);
CREATE INDEX IF NOT EXISTS idx_stages_run ON stages(run_id);
CREATE INDEX IF NOT EXISTS idx_metrics_run_step ON metrics(run_id, step);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
"""

def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)

def _as_int(value: Any) -> int | None:
    return int(value) if value is not None else None

def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


class ExperimentDB:
    """Durable, queryable experiment store backed by one SQLite file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(_SCHEMA)
        self.conn.execute(
            "INSERT INTO schema_metadata(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def sync_manifest(self, manifest: dict[str, Any]) -> None:
        """Project the authoritative run manifest into normalized SQLite tables."""
        run_id = str(manifest["run_id"])
        experiment_id = str(manifest["experiment_id"])
        ts = manifest.get("timestamps") or {}
        git = manifest.get("git") or {}
        now = ts.get("updated") or ts.get("started") or ""
        self.conn.execute(
            "INSERT INTO experiments(id,name,description,status,created_at,updated_at,tags_json) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at",
            (experiment_id, experiment_id, "Model Lab experiment", manifest.get("final_status","RUNNING"),
             ts.get("started") or now, now, "[]"),
        )
        self.conn.execute(
            "INSERT INTO runs(id,experiment_id,dataset_id,started_at,completed_at,status,git_sha,git_branch,git_dirty,entrypoint,parent_run_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,status=excluded.status,"
            "git_sha=excluded.git_sha,git_branch=excluded.git_branch,git_dirty=excluded.git_dirty",
            (run_id, experiment_id, manifest.get("dataset_id"), ts.get("started") or now, ts.get("ended"),
             manifest.get("final_status","RUNNING"), git.get("commit"), git.get("branch"),
             int(bool(git.get("dirty"))), "run_pipeline.py", None),
        )
        self._sync_hardware(run_id, manifest.get("hardware") or {})
        self._sync_dataset(run_id, manifest)
        self._sync_configs(run_id, manifest.get("configuration") or {})
        self._sync_stages(run_id, manifest.get("stages") or {})
        self._sync_artifacts(run_id, manifest.get("artifacts") or [])
        self._sync_warnings_errors(run_id, manifest.get("warnings") or [], manifest.get("errors") or [])
        self.conn.commit()

    def _sync_hardware(self, run_id: str, hardware: dict[str, Any]) -> None:
        host = hardware.get("host") if isinstance(hardware.get("host"), dict) else hardware
        torch = hardware.get("torch") if isinstance(hardware.get("torch"), dict) else {}
        self.conn.execute(
            "INSERT INTO hardware(run_id,platform,cpu_name,cpu_threads,ram_gb,gpu_name,gpu_count,gpu_memory_gb,cuda_version,driver_version,pytorch_version,disk_free_gb,disk_total_gb,snapshot_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET snapshot_json=excluded.snapshot_json,"
            "platform=excluded.platform,cpu_name=excluded.cpu_name,cpu_threads=excluded.cpu_threads,ram_gb=excluded.ram_gb,"
            "gpu_name=excluded.gpu_name,gpu_count=excluded.gpu_count,gpu_memory_gb=excluded.gpu_memory_gb,cuda_version=excluded.cuda_version,"
            "driver_version=excluded.driver_version,pytorch_version=excluded.pytorch_version",
            (run_id, host.get("platform"), host.get("cpu_name"), _as_int(host.get("cpu_threads")),
             _as_float(host.get("total_ram_gb") or host.get("ram_gb")), host.get("gpu_name"),
             _as_int(host.get("gpu_count") or torch.get("device_count")), _as_float(host.get("gpu_memory_gb")),
             host.get("cuda_version") or torch.get("cuda_version"), host.get("driver_version"),
             host.get("pytorch_version") or torch.get("version"), _as_float(host.get("disk_free_gb")),
             _as_float(host.get("disk_total_gb")), _json(hardware)),
        )

    def _sync_dataset(self, run_id: str, manifest: dict[str, Any]) -> None:
        identity = manifest.get("dataset_identity") or {}
        dataset_id = str(manifest.get("dataset_id") or identity.get("dataset_id") or "")
        if not dataset_id:
            return
        report = manifest.get("dataset_report") or {}
        self.conn.execute(
            "INSERT INTO datasets(id,run_id,dataset_group,manifest_sha256,document_count,token_count,train_tokens,validation_tokens) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET dataset_group=excluded.dataset_group,manifest_sha256=excluded.manifest_sha256",
            (dataset_id, run_id, identity.get("requested_group") or identity.get("group_id"),
             report.get("sha256"), None, None, None, None),
        )

    def _sync_configs(self, run_id: str, configs: dict[str, Any]) -> None:
        for kind, value in configs.items():
            if isinstance(value, dict):
                digest = value.get("sha256") or value.get("config_sha256")
                path = value.get("path")
                snapshot = value
            else:
                digest, path, snapshot = str(value), None, {"identity": value}
            self.conn.execute(
                "INSERT INTO configs(run_id,config_type,sha256,path,snapshot_json) VALUES(?,?,?,?,?) "
                "ON CONFLICT(run_id,config_type) DO UPDATE SET sha256=excluded.sha256,path=excluded.path,snapshot_json=excluded.snapshot_json",
                (run_id, str(kind), digest, path, _json(snapshot)),
            )

    def _sync_stages(self, run_id: str, stages: dict[str, Any]) -> None:
        for name, stage in stages.items():
            metrics = stage.get("metrics") if isinstance(stage.get("metrics"), dict) else {}
            self.conn.execute(
                "INSERT INTO stages(run_id,stage_name,status,started_at,completed_at,duration_seconds,records_in,records_out,tokens,throughput,input_artifact_id,output_artifact_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,stage_name) DO UPDATE SET status=excluded.status,started_at=excluded.started_at,"
                "completed_at=excluded.completed_at,duration_seconds=excluded.duration_seconds,records_in=excluded.records_in,records_out=excluded.records_out,"
                "tokens=excluded.tokens,throughput=excluded.throughput",
                (run_id, name, stage.get("status","PENDING"), stage.get("start"), stage.get("end"),
                 _as_float(stage.get("duration_seconds")), _as_int(metrics.get("input_document_count")),
                 _as_int(metrics.get("document_count") or metrics.get("output_document_count")),
                 _as_int(metrics.get("token_count")), _as_float(metrics.get("throughput_docs_per_second")), None, None),
            )

    def _sync_artifacts(self, run_id: str, artifacts: Iterable[dict[str, Any]]) -> None:
        for item in artifacts:
            artifact_id = str(item.get("artifact_id") or f"{run_id}:{item.get('stage')}:{item.get('path')}")
            path = str(item.get("path",""))
            size = None
            try:
                candidate = self.path.parent / path
                if candidate.is_file():
                    size = candidate.stat().st_size
            except OSError:
                pass
            self.conn.execute(
                "INSERT INTO artifacts(id,run_id,stage_name,path,sha256,size_bytes,created_at,parent_artifact_id,metadata_json) "
                "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET sha256=excluded.sha256,size_bytes=excluded.size_bytes,metadata_json=excluded.metadata_json",
                (artifact_id, run_id, item.get("stage"), path, item.get("sha256"), size,
                 None, None, _json(item)),
            )

    def _sync_warnings_errors(self, run_id: str, warnings: list[Any], errors: list[Any]) -> None:
        self.conn.execute("DELETE FROM warnings WHERE run_id=?", (run_id,))
        self.conn.execute("DELETE FROM errors WHERE run_id=?", (run_id,))
        for item in warnings:
            row = item if isinstance(item, dict) else {"message": str(item)}
            self.conn.execute("INSERT INTO warnings(run_id,stage_id,code,message,created_at) VALUES(?,?,?,?,?)",
                              (run_id, None, row.get("code"), str(row.get("message", row)), row.get("created_at")))
        for item in errors:
            row = item if isinstance(item, dict) else {"message": str(item)}
            self.conn.execute("INSERT INTO errors(run_id,stage_id,code,message,exception_type,created_at) VALUES(?,?,?,?,?,?)",
                              (run_id, None, row.get("code"), str(row.get("message", row)), row.get("exception_type"), row.get("created_at")))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT r.*,e.name AS experiment_name FROM runs r JOIN experiments e ON e.id=r.experiment_id WHERE r.id=?",
            (run_id,),
        ).fetchone()
        return dict(row) if row else None

    def search_runs(self, *, status: str | None = None, git_sha: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("status=?"); params.append(status)
        if git_sha:
            clauses.append("git_sha=?"); params.append(git_sha)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(f"SELECT * FROM runs{where} ORDER BY started_at DESC LIMIT ?", (*params, int(limit))).fetchall()
        return [dict(row) for row in rows]

    def compare_runs(self, run_a: str, run_b: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, query in {
            "runs": "SELECT * FROM runs WHERE id IN (?,?)",
            "hardware": "SELECT * FROM hardware WHERE run_id IN (?,?)",
            "stages": "SELECT * FROM stages WHERE run_id IN (?,?) ORDER BY stage_name",
            "artifacts": "SELECT * FROM artifacts WHERE run_id IN (?,?) ORDER BY stage_name,path",
        }.items():
            result[key] = [dict(row) for row in self.conn.execute(query, (run_a, run_b)).fetchall()]
        return result

    def lineage(self, run_id: str) -> dict[str, Any]:
        return {
            "run": self.get_run(run_id),
            "dataset": [dict(r) for r in self.conn.execute("SELECT * FROM datasets WHERE run_id=?", (run_id,)).fetchall()],
            "stages": [dict(r) for r in self.conn.execute("SELECT * FROM stages WHERE run_id=? ORDER BY id", (run_id,)).fetchall()],
            "artifacts": [dict(r) for r in self.conn.execute("SELECT * FROM artifacts WHERE run_id=? ORDER BY stage_name,path", (run_id,)).fetchall()],
            "configs": [dict(r) for r in self.conn.execute("SELECT * FROM configs WHERE run_id=? ORDER BY config_type", (run_id,)).fetchall()],
        }


__all__ = ["ExperimentDB", "SCHEMA_VERSION"]
