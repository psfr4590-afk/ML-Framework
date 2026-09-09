from __future__ import annotations

from pathlib import Path

from .config import load_groups
from .runner import start_stage, stop
from .secrets import credentials
from .store import store

STAGES = ("crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export")


def init():
    return store.ensure_seed_datasets()


def add(name, description="", group_id=None):
    return store.create(name, description, group_id=group_id)


def ingest(did, path):
    return store.ingest_path(did, Path(path))


def stage(did, name):
    if name not in STAGES:
        raise ValueError(f"Unknown stage: {name}. Valid stages: {', '.join(STAGES)}")
    return start_stage(did, name)


def status(did=None):
    return store.refresh_pipeline_state(did) if did else [store.refresh_pipeline_state(d["id"]) for d in store.list()]


def groups():
    return load_groups()


def credential_list():
    return credentials.list()


def credential_set(name, secret, provider="custom", kind="token", env_var="", description="", identity=""):
    return credentials.set(name, secret, provider, kind, env_var, description, identity)


def credential_delete(name):
    return credentials.delete(name)


def credential_test(name):
    return credentials.test(name)


def crawl_stats(did):
    return store.crawl_stats(did)


def crawl_domains(did):
    return store.crawl_domains(did)


def crawl_log(did, tail=80):
    return store.crawl_log(did, tail)
