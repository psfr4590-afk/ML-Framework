from __future__ import annotations

import platform
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .runner import stop
from .service import (
    add,
    credential_delete,
    credential_list,
    credential_set,
    credential_test,
    groups,
    ingest,
    init,
    stage,
    status,
)
from .store import store

app = FastAPI(title="M²S Model Training Pipeline", version="1.3.0")


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


@app.on_event("startup")
def startup():
    init()


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(
        "<html><body><h1>M²S MODEL TRAINING PIPELINE</h1>"
        "<p>Local command center</p></body></html>"
    )


@app.get("/api/system")
def system():
    return {
        "application": "M²S Model Training Pipeline",
        "version": "1.3.0",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "hostname": platform.node(),
        "stages": list(store.STAGES) if hasattr(store, "STAGES") else [
            "crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"
        ],
    }


@app.get("/api/datasets")
def datasets():
    return status()


@app.post("/api/datasets")
def create(x: DatasetCreate):
    return add(x.name, x.description, x.group_id)


@app.get("/api/datasets/{did}")
def dataset(did: int):
    d = status(did)
    if not d:
        raise HTTPException(404, "Dataset not found")
    d["events"] = store.tail_events(did)
    return d


@app.post("/api/datasets/{did}/ingest")
def ingest_dataset(did: int, x: DatasetIngest):
    try:
        return ingest(did, x.path)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/datasets/{did}/stage/{name}")
def run_stage(did: int, name: str):
    try:
        return stage(did, name)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/datasets/{did}/stop")
def stop_stage(did: int):
    return {"stopped": stop(did)}


@app.get("/api/groups")
def api_groups():
    return groups()


@app.get("/api/credentials")
def creds():
    return credential_list()


@app.post("/api/credentials")
def set_cred(x: CredentialSet):
    try:
        return credential_set(x.name, x.secret, x.provider, x.kind, x.env_var, x.description, x.identity)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/credentials/{name}/test")
def test_cred(name: str):
    return credential_test(name)


@app.delete("/api/credentials/{name}")
def del_cred(name: str):
    return {"deleted": credential_delete(name)}


@app.get("/api/datasets/{did}/crawl/stats")
def crawl_stats(did: int):
    return store.crawl_stats(did)


@app.get("/api/datasets/{did}/crawl/domains")
def crawl_domains(did: int):
    return store.crawl_domains(did)


@app.get("/api/datasets/{did}/crawl/log")
def crawl_log(did: int, tail: int = 80):
    return store.crawl_log(did, tail)
