from __future__ import annotations
import json, os, shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from pipeline.integrity import artifact_valid, sha256_file
from .config import DATASETS, group_by_id, load_groups

LOCK = RLock()
STAGES = ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class DatasetStore:
    def __init__(self):
        DATASETS.mkdir(parents=True, exist_ok=True)

    def path(self, did): return DATASETS / f"dataset_{int(did):03d}"
    def output_path(self, did): return self.path(did) / "output"
    def _ids(self): return sorted(int(p.name[8:]) for p in DATASETS.glob("dataset_*") if p.is_dir() and p.name[8:].isdigit())
    def next_id(self):
        ids = self._ids()
        return ids[-1] + 1 if ids else 1

    def get(self, did):
        p = self.path(did) / "dataset.json"
        if not p.exists(): return None
        return json.loads(p.read_text(encoding="utf-8"))

    def list(self): return [self.get(i) for i in self._ids()]

    def create(self, name, description="", group_id=None, group_config=None):
        with LOCK:
            did = self.next_id()
            group = group_by_id(group_id) if group_id else (group_config or {"id": f"custom_{did:03d}", "name": name, "sources": {}})
            if group_id and not group: raise ValueError(f"Unknown dataset group: {group_id}")
            root = self.path(did); root.mkdir(parents=True, exist_ok=True)
            for d in ("raw", "logs", "errors", "output", "scratch"): (root / d).mkdir(exist_ok=True)
            stages = {s: "pending" for s in STAGES}
            meta = {"id": did, "name": name.strip() or f"Dataset {did}", "description": description,
                    "group_id": group.get("id"), "group": group, "status": "NEW", "stages": stages,
                    "stats": {"files": 0, "bytes": 0, "documents": 0, "words": 0}, "events": [],
                    "created_at": now(), "updated_at": now()}
            atomic_json(root / "dataset.json", meta); self.ensure_files(did); return meta

    def ensure_files(self, did):
        root = self.path(did); (root / "events.jsonl").touch(exist_ok=True); return root

    def ensure_seed_datasets(self):
        existing = self.list(); gids = {d.get("group_id") for d in existing}
        for g in load_groups():
            if g.get("id") not in gids: self.create(g.get("name", g.get("id", "dataset")), group_id=g.get("id"))
        return self.list()

    def update(self, did, **changes):
        d = self.get(did)
        if not d: raise KeyError(did)
        d.update(changes); d["updated_at"] = now(); atomic_json(self.path(did) / "dataset.json", d); return d

    def event(self, did, event, data=None):
        item = {"ts": now(), "event": event, "data": data or {}}
        with (self.path(did) / "events.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def tail_events(self, did, limit=150):
        p = self.path(did) / "events.jsonl"
        if not p.exists(): return []
        from collections import deque
        with p.open(encoding="utf-8", errors="replace") as f: return list(deque((json.loads(x) for x in f if x.strip()), maxlen=limit))

    def refresh_stats(self, did):
        root = self.path(did); files = bytes_ = docs = words = 0
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts and ".runtime" not in p.parts:
                files += 1; bytes_ += p.stat().st_size
        for c in (root / "scratch" / "04_weighted.jsonl", root / "scratch" / "03_deduped.jsonl", root / "scratch" / "02_cleaned.jsonl"):
            if c.exists():
                for line in c.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.strip():
                        docs += 1
                        try: words += len(str(json.loads(line).get("text", "")).split())
                        except Exception: pass
                break
        d = self.get(did); d["stats"] = {**d.get("stats", {}), "files": files, "bytes": bytes_, "documents": docs, "words": words}; d["updated_at"] = now(); atomic_json(root / "dataset.json", d); return d["stats"]

    def ingest_path(self, did, source: Path):
        source = source.resolve(); root = self.path(did); dest = root / "raw"
        if not source.exists(): raise FileNotFoundError(source)
        paths = [source] if source.is_file() else [p for p in source.rglob("*") if p.is_file()]
        for p in paths:
            rel = p.name if source.is_file() else p.relative_to(source).as_posix(); target = dest / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
        stages = self.get(did)["stages"]; stages["crawl"] = "complete"; self.update(did, status="COLLECTED", stages=stages); self.refresh_stats(did); self.event(did, "ingest.completed", {"files": len(paths)}); return self.get(did)

    def _verified_stage(self, stage, paths):
        paths = [p for p in paths if p is not None]
        if not paths: return "pending"
        if stage in {"crawl", "clean", "dedup", "weight", "tokenize"}:
            return "complete" if all(artifact_valid(p) for p in paths) else "stale"
        if stage == "shard":
            marker = paths[0].parent / "shards.manifest.json"
            if not marker.is_file(): return "stale"
            try:
                data = json.loads(marker.read_text(encoding="utf-8")); files = data.get("files", [])
                if not files: return "corrupt"
                valid = all((marker.parent / item["name"]).is_file() and (marker.parent / item["name"]).stat().st_size == int(item["size"]) and sha256_file(marker.parent / item["name"]) == item["sha256"] for item in files)
                return "complete" if valid else "corrupt"
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError): return "corrupt"
        if stage == "train":
            return "complete" if any(artifact_valid(p) for p in paths) else "stale"
        if stage == "export":
            manifest = paths[0]
            if not manifest.is_file() or manifest.stat().st_size <= 0: return "pending"
            try:
                data = json.loads(manifest.read_text(encoding="utf-8")); final = Path(data["final_gguf"])
                if not final.is_file() or final.stat().st_size != int(data["final_gguf_size"]): return "stale"
                if sha256_file(final) != data["final_gguf_sha256"]: return "corrupt"
                modelfile = Path(data["modelfile"])
                return "complete" if modelfile.is_file() and modelfile.stat().st_size > 0 else "stale"
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError): return "corrupt"
        return "pending"

    def refresh_pipeline_state(self, did):
        d = self.get(did)
        if not d: return None
        self.refresh_stats(did); d = self.get(did); root = self.path(did); out = root / "output"; scratch = root / "scratch"
        checks = {
            "crawl": list(scratch.glob("01_crawled*.jsonl")), "clean": [scratch / "02_cleaned.jsonl"],
            "dedup": [scratch / "03_deduped.jsonl"], "weight": [scratch / "04_weighted.jsonl"],
            "tokenize": [out / "tokenizer" / "tokenizer.json"], "shard": list((out / "shards").glob("shard_*.bin")),
            "train": list((out / "checkpoints").glob("ckpt_final_*.pt")),
            "export": [out / "gguf" / "export_manifest.json"],
        }
        states = {s: self._verified_stage(s, checks[s]) for s in STAGES}
        for s, state in states.items():
            if d["stages"].get(s) != "running": d["stages"][s] = state
        if any(v == "corrupt" for v in states.values()): d["status"] = "CORRUPT"
        elif any(v == "stale" for v in states.values()): d["status"] = "STALE"
        elif states["export"] == "complete": d["status"] = "COMPLETE"
        elif states["train"] == "complete": d["status"] = "TRAINED"
        elif any(v == "running" for v in d["stages"].values()): d["status"] = "RUNNING"
        elif any(v == "complete" for v in states.values()): d["status"] = "IN_PROGRESS"
        else: d["status"] = d.get("status", "NEW")
        atomic_json(root / "dataset.json", d); return d

    def crawl_stats(self, did): return self._json_or_empty(self.path(did) / "scratch" / "crawl_stats.json")
    def crawl_domains(self, did): return self._json_or_empty(self.path(did) / "scratch" / "crawl_domains.json")
    def crawl_log(self, did, tail=80):
        p = self.path(did) / "logs" / "command-center.log"
        if not p.exists(): return []
        from collections import deque
        with p.open(encoding="utf-8", errors="replace") as f: return list(deque((x.rstrip() for x in f), maxlen=max(1, min(int(tail), 1000))))

    def _json_or_empty(self, p):
        try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception: return {}


store = DatasetStore()
