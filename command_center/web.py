from __future__ import annotations

from contextlib import asynccontextmanager
import platform
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from .runner import stop
from .service import add, credential_delete, credential_list, credential_set, credential_test, groups, ingest, init, stage, status
from .store import store

LOCAL_ORIGINS = {"http://127.0.0.1", "http://localhost", "http://[::1]"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CONTROL_HEADER = "x-m2s-command-center"


class LocalhostOnlyMiddleware(BaseHTTPMiddleware):
    """Keep the API local and require a non-forgeable browser custom header for mutations."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            client_host = request.client.host if request.client else None
            if client_host not in ("127.0.0.1", "::1"):
                return JSONResponse(status_code=403, content={"error": {"code": "LOCAL_ONLY", "message": "Local API access required"}})
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
    name: str
    secret: str
    provider: str = "custom"
    kind: str = "token"
    env_var: str = ""
    description: str = ""
    identity: str = ""


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    group_id: str | None = None


class DatasetIngest(BaseModel):
    path: str


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
def crawl_log(did: int, tail: int = 80): return store.crawl_log(did, tail)
