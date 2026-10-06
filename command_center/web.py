from __future__ import annotations

from contextlib import asynccontextmanager
import json
from datetime import datetime, timezone
import platform
import sys

from fastapi import FastAPI, HTTPException, Request
from pydantic import Field
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from .runner import stop
from .config import ROOT
from pipeline.experiment_db import ExperimentDB
from .service import add, credential_delete, credential_list, credential_set, credential_test, groups, ingest, init, stage, status
from .store import store
from .security import MAX_REQUEST_BYTES, validate_tail_lines

LOCAL_ORIGINS = {"http://127.0.0.1", "http://localhost", "http://[::1]"}
LOCAL_CLIENT_HOSTS = {"127.0.0.1", "::1", "testclient", "testserver"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CONTROL_HEADER = "x-m2s-command-center"


class LocalhostOnlyMiddleware(BaseHTTPMiddleware):
    """Keep the API local and require a non-forgeable browser custom header for mutations."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_REQUEST_BYTES:
                        return JSONResponse(status_code=413, content={"error": {"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds the command-center limit"}})
                except ValueError:
                    return JSONResponse(status_code=400, content={"error": {"code": "INVALID_CONTENT_LENGTH", "message": "Invalid Content-Length"}})
            client_host = request.client.host if request.client else None
            if client_host not in LOCAL_CLIENT_HOSTS:
                message = "Command center is localhost-only."
                return JSONResponse(status_code=403, content={"detail": message, "error": {"code": "LOCAL_ONLY", "message": message}})
            if request.method in MUTATING_METHODS:
                origin = request.headers.get("origin")
                if origin and origin not in LOCAL_ORIGINS:
                    return JSONResponse(status_code=403, content={"error": {"code": "ORIGIN_REJECTED", "message": "Cross-origin control requests are not permitted"}})
                if request.headers.get(CONTROL_HEADER) != "1":
                    return JSONResponse(status_code=403, content={"error": {"code": "CONTROL_HEADER_REQUIRED", "message": "Command-center control header required"}})
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init()
    yield


app = FastAPI(title="M²S Model Training Pipeline", version="1.3.0", lifespan=lifespan)
app.add_middleware(LocalhostOnlyMiddleware)


class CredentialSet(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    secret: str = Field(min_length=1, max_length=65536)
    provider: str = Field(default="custom", max_length=128)
    kind: str = Field(default="token", max_length=64)
    env_var: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=4096)
    identity: str = Field(default="", max_length=4096)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4096)
    group_id: str | None = Field(default=None, max_length=128)


class DatasetIngest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


def _safe_error(exc: Exception, code: str = "REQUEST_FAILED") -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, {"code": "NOT_FOUND", "message": "Requested resource was not found"})
    if isinstance(exc, ValueError):
        return HTTPException(400, {"code": code, "message": "Request validation failed"})
    return HTTPException(500, {"code": "INTERNAL_ERROR", "message": "Request could not be completed"})


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>M²S Model Training Pipeline</title><style>:root{color-scheme:dark;--bg:#0b1020;--panel:#121a2b;--border:#26324a;--text:#eef3ff;--muted:#9eabc4;--accent:#79a7ff;--ok:#63d49b}*{box-sizing:border-box}body{margin:0;min-height:100vh;font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--text);background:radial-gradient(circle at 15% 0%,#18284a 0,transparent 42%),var(--bg)}main{width:min(1040px,calc(100% - 40px));margin:0 auto;padding:72px 0 56px}.eyebrow{color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px}h1{margin:10px 0 12px;font-size:clamp(34px,6vw,58px);line-height:1.05;letter-spacing:-.035em}.lead{max-width:720px;color:var(--muted);font-size:18px;margin:0 0 34px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.card{background:color-mix(in srgb,var(--panel) 92%,transparent);border:1px solid var(--border);border-radius:18px;padding:22px;box-shadow:0 14px 40px #0003}.card h2{margin:0 0 7px;font-size:17px}.card p{margin:0;color:var(--muted)}.pill{display:inline-block;margin-top:14px;padding:4px 9px;border:1px solid #34506f;border-radius:999px;color:var(--ok);font-size:12px;font-weight:700}code{color:#cfe0ff;background:#0a1120;padding:2px 6px;border-radius:6px}footer{margin-top:34px;color:var(--muted);font-size:13px}a{color:var(--accent);text-decoration:none}@media(max-width:760px){main{padding-top:42px}.grid{grid-template-columns:1fr}}</style></head><body><main><div class="eyebrow">Model Lab · Local Command Center</div><h1>M²S Model Training Pipeline</h1><p class="lead">A local-first control surface for dataset preparation, training, artifact verification, and GGUF export. The browser surface is intentionally localhost-only.</p><section class="grid" aria-label="Command center capabilities"><article class="card"><h2>Dataset lifecycle</h2><p>Create datasets, inspect pipeline state, ingest local sources, and monitor crawl telemetry.</p><span class="pill">/api/datasets</span></article><article class="card"><h2>Pipeline control</h2><p>Run individual stages or inspect the configured stage graph without exposing a remote control plane.</p><span class="pill">8 stages</span></article><article class="card"><h2>Machine status</h2><p>Read runtime and host information through the local system endpoint.</p><span class="pill">/api/system</span></article></section><footer>API documentation: <a href="/docs">/docs</a> · OpenAPI schema: <a href="/openapi.json">/openapi.json</a></footer></main></body></html>""")


@app.get("/api/system")
def system():
    return {"application":"M²S Model Training Pipeline","version":"1.3.0","platform":sys.platform,"python":sys.version.split()[0],"machine":platform.machine(),"stages":list(store.STAGES) if hasattr(store,"STAGES") else ["crawl","clean","dedup","weight","tokenize","shard","train","export"],"security":{"api_access":"localhost-only","mutation_control":"custom-header"}}



def _experiment_db() -> ExperimentDB:
    return ExperimentDB(ROOT / "output" / "experiment.db")


def _rows(db: ExperimentDB, query: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in db.conn.execute(query, params).fetchall()]


def _latest_run(db: ExperimentDB) -> dict | None:
    rows = _rows(db, "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1")
    return rows[0] if rows else None


def _run_snapshot(run_id: str | None = None) -> dict:
    db = _experiment_db()
    run = db.get_run(run_id) if run_id else _latest_run(db)
    if not run:
        return {"run": None, "stage": [], "training": {}, "dataset": {}, "hardware": {}, "provenance": {}, "checkpoints": [], "artifacts": [], "warnings": [], "errors": []}
    rid = run["id"]
    dataset_rows = _rows(db, "SELECT * FROM datasets WHERE run_id=? ORDER BY id LIMIT 1", (rid,))
    dataset = dataset_rows[0] if dataset_rows else {}
    stages = _rows(db, "SELECT * FROM stages WHERE run_id=? ORDER BY id", (rid,))
    metrics = _rows(db, "SELECT step,metric_name,metric_value,metric_unit,recorded_at FROM metrics WHERE run_id=? ORDER BY step DESC,id DESC", (rid,))
    latest = {}
    for row in metrics:
        latest.setdefault(row["metric_name"], row)
    checkpoints = _rows(db, "SELECT * FROM checkpoints WHERE run_id=? ORDER BY step DESC", (rid,))
    artifacts = _rows(db, "SELECT id,stage_name,path,sha256,size_bytes,created_at FROM artifacts WHERE run_id=? ORDER BY stage_name,path", (rid,))
    configs = _rows(db, "SELECT config_type,sha256,path,snapshot_json FROM configs WHERE run_id=? ORDER BY config_type", (rid,))
    train_config = {}
    for cfg in configs:
        if cfg.get("config_type") in {"train", "training"}:
            try:
                train_config = json.loads(cfg.get("snapshot_json") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                train_config = {}
    sources = _rows(db, "SELECT s.id,s.kind,s.identifier,s.revision,s.license,s.status,ss.requests,ss.successes,ss.failures,ss.documents,ss.retries,ss.duration_seconds FROM sources s LEFT JOIN source_stats ss ON ss.source_id=s.id WHERE s.dataset_id=? ORDER BY s.id", (dataset["id"],)) if dataset.get("id") else []
    warnings = _rows(db, "SELECT code,message,created_at FROM warnings WHERE run_id=? ORDER BY id DESC", (rid,))
    errors = _rows(db, "SELECT code,message,exception_type,created_at FROM errors WHERE run_id=? ORDER BY id DESC", (rid,))
    runtime = _rows(db, "SELECT * FROM runtime_estimates WHERE run_id=? ORDER BY id DESC", (rid,))
    step = next((int(r["step"]) for r in metrics if r["step"] is not None), None)
    total_steps = next((int(latest[k]["metric_value"]) for k in ("total_steps", "train.total_steps") if k in latest), None)
    if total_steps is None:
        raw_total = train_config.get("total_steps")
        if raw_total is not None:
            try:
                total_steps = int(raw_total)
            except (TypeError, ValueError):
                total_steps = None
    progress = step / total_steps if step is not None and total_steps else None
    def metric_value(*names):
        return next((latest[n]["metric_value"] for n in names if n in latest), None)
    train_runtime = next((r for r in runtime if r["estimate_type"] == "training"), {})
    elapsed_seconds = None
    if run.get("started_at"):
        try:
            start = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(run["completed_at"].replace("Z", "+00:00")) if run.get("completed_at") else datetime.now(timezone.utc)
            elapsed_seconds = max(0.0, (end - start).total_seconds())
        except (TypeError, ValueError):
            elapsed_seconds = None
    eta_seconds = None
    if progress and progress > 0 and elapsed_seconds is not None and not run.get("completed_at"):
        eta_seconds = max(0.0, elapsed_seconds * (1.0 - progress) / progress)
    hardware_rows = _rows(db, "SELECT * FROM hardware WHERE run_id=? LIMIT 1", (rid,))
    hardware = hardware_rows[0] if hardware_rows else {}
    if hardware.get("snapshot_json"):
        try:
            snapshot = json.loads(hardware["snapshot_json"])
            if isinstance(snapshot, dict):
                hardware["gpu_utilization"] = snapshot.get("gpu_utilization_percent", snapshot.get("gpu_utilization"))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return {
        "run": run,
        "stage": stages,
        "training": {
            "step": step, "total_steps": total_steps, "progress": progress,
            "loss": metric_value("loss", "train.loss", "train_loss"),
            "validation_loss": metric_value("val_loss", "validation_loss", "train.val_loss"),
            "best_loss": next((c["best_val_loss"] for c in checkpoints if c["best_val_loss"] is not None), None),
            "tokens_per_sec": metric_value("tokens_per_sec", "tokens/sec", "train.tokens_per_sec"),
            "estimated_seconds": train_runtime.get("estimated_seconds"),
            "actual_seconds": train_runtime.get("actual_seconds"),
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
        },
        "dataset": {**dataset, "sources": sources, "model": train_config.get("model_preset") or train_config.get("model_name")},
        "hardware": hardware,
        "provenance": {
            "configuration": bool(configs),
            "dataset_lineage": bool(dataset.get("manifest_sha256")),
            "tokenizer": any(a["stage_name"] == "tokenize" and a["sha256"] for a in artifacts),
            "checkpoint": bool(checkpoints),
            "artifact_integrity": bool(artifacts) and all(a["sha256"] for a in artifacts),
            "configs": configs,
        },
        "checkpoints": checkpoints, "artifacts": artifacts, "warnings": warnings, "errors": errors,
    }


@app.get("/api/runs")
def api_runs(limit: int = 20):
    return {"runs": _experiment_db().search_runs(limit=max(1, min(int(limit), 100)))}


@app.get("/api/runs/{run_id}")
def api_run(run_id: str):
    snapshot = _run_snapshot(run_id)
    if not snapshot["run"]:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Run not found"})
    return snapshot


@app.get("/api/dashboard")
def api_dashboard():
    return _run_snapshot()

@app.get("/api/datasets")
def datasets(): return status()


@app.post("/api/datasets")
def create(x: DatasetCreate):
    try: return add(x.name, x.description, x.group_id)
    except Exception as exc: raise _safe_error(exc) from exc


@app.get("/api/datasets/{did}")
def dataset(did: int):
    d = status(did)
    if not d: raise HTTPException(404, {"code":"NOT_FOUND","message":"Dataset not found"})
    d["events"] = store.tail_events(did)
    return d


@app.post("/api/datasets/{did}/ingest")
def ingest_dataset(did: int, x: DatasetIngest):
    try: return ingest(did, x.path)
    except Exception as exc: raise _safe_error(exc) from exc


@app.post("/api/datasets/{did}/stage/{name}")
def run_stage(did: int, name: str):
    try: return stage(did, name)
    except Exception as exc: raise _safe_error(exc) from exc


@app.post("/api/datasets/{did}/stop")
def stop_stage(did: int):
    try: return {"stopped": stop(did)}
    except Exception as exc: raise _safe_error(exc) from exc


@app.get("/api/groups")
def api_groups(): return groups()


@app.get("/api/credentials")
def creds(): return credential_list()


@app.post("/api/credentials")
def set_cred(x: CredentialSet):
    try: return credential_set(x.name, x.secret, x.provider, x.kind, x.env_var, x.description, x.identity)
    except Exception as exc: raise _safe_error(exc) from exc


@app.post("/api/credentials/{name}/test")
def test_cred(name: str):
    try: return credential_test(name)
    except Exception as exc: raise _safe_error(exc) from exc


@app.delete("/api/credentials/{name}")
def del_cred(name: str):
    try: return {"deleted": credential_delete(name)}
    except Exception as exc: raise _safe_error(exc) from exc


@app.get("/api/datasets/{did}/crawl/stats")
def crawl_stats(did: int): return store.crawl_stats(did)
@app.get("/api/datasets/{did}/crawl/domains")
def crawl_domains(did: int): return store.crawl_domains(did)
@app.get("/api/datasets/{did}/crawl/log")
def crawl_log(did: int, tail: int = 80): return store.crawl_log(did, validate_tail_lines(tail))
