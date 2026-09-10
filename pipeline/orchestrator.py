"""Pipeline orchestration for the Model Lab end-to-end training flow."""
from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

from pipeline.config_validation import validate_config
from pipeline.integrity import artifact_valid, atomic_jsonl_write, sha256_file, write_manifest
from pipeline.types import Document
from pipeline.crawler.source_scorer import DomainSignalTracker, SourceWeightLookup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("orchestrator")

STAGE_IMPLEMENTATIONS = {
    "crawl": ("pipeline.crawler.web_crawler", "WebCrawler"),
    "clean": ("pipeline.cleaner.cleaner", "Cleaner"),
    "dedup": ("pipeline.embedder.semantic_dedup", "SemanticDeduplicator"),
    "weight": ("pipeline.weighter.weighter", "DomainWeighter"),
    "tokenize": ("pipeline.tokenizer.train_tokenizer", "BPETokenizerTrainer"),
    "shard": ("pipeline.shardwriter.shard_writer", "ShardWriter"),
    "train": ("pipeline.trainer.train", "Trainer"),
    "export": ("scripts.export_gguf", "export_checkpoint"),
}

SOURCE_KINDS = ("web", "github", "arxiv", "huggingface", "google")
REQUIRED_SOURCE_FIELDS = {"kind", "identifier", "revision", "license", "raw_source_sha256"}


def _setup_logging(out_dir: Path, level: str = "INFO") -> None:
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(name)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not any(getattr(h, "_model_lab_console", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        handler._model_lab_console = True
        root.addHandler(handler)
    log_file = (log_dir / "pipeline.log").resolve()
    if not any(getattr(h, "_model_lab_file", None) == str(log_file) for h in root.handlers):
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(fmt)
        handler._model_lab_file = str(log_file)
        root.addHandler(handler)


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _hash_value(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _jsonl_write(docs: Iterator[Document], path: Path, kind: str = "jsonl", provenance: dict[str, Any] | None = None) -> int:
    count = atomic_jsonl_write(path, lambda: (doc.to_jsonl() for doc in docs))
    write_manifest(path, kind=kind, rows=count, provenance=provenance)
    log.info("Wrote %d docs → %s", count, path)
    return count


def _jsonl_read(path: Path) -> Iterator[Document]:
    if not path.exists():
        raise FileNotFoundError(f"Required pipeline input does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TypeError("record is not an object")
                yield Document.from_dict(record)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise RuntimeError(f"Input integrity failure at {path}:{line_no}: {exc}") from exc


def _load_class(module: str, name: str):
    return getattr(importlib.import_module(module), name)


def _implementation_sha256(stage: str) -> str:
    module_name, class_name = STAGE_IMPLEMENTATIONS[stage]
    module = importlib.import_module(module_name)
    target = getattr(module, class_name)
    source = Path(inspect.getsourcefile(target) or module.__file__ or "").resolve()
    digest = hashlib.sha256()
    digest.update(sha256_file(Path(__file__).resolve()).encode())
    if source.is_file():
        digest.update(sha256_file(source).encode())
    return digest.hexdigest()


def _source_definition_paths(cfg: dict, root: Path) -> dict[str, Path]:
    crawl = cfg.get("crawl", {})
    configured_path = cfg.get("_pipeline_config_path")
    pipeline_config = Path(configured_path) if configured_path else root / "config" / "pipeline_config.yaml"
    if not pipeline_config.is_absolute():
        pipeline_config = root / pipeline_config
    paths = {
        "pipeline_config": pipeline_config,
        "source_weights": root / str(crawl.get("source_weights_file", "config/source_weights.yaml")),
        "dataset_groups": root / str(crawl.get("dataset_groups_file", "config/dataset_groups.yaml")),
    }
    web = crawl.get("web", {})
    if web.get("seed_urls_file"):
        paths["seed_urls"] = root / str(web["seed_urls_file"])
    return {name: path.resolve() for name, path in paths.items()}


def _source_entry(kind: str, identifier: str, revision: str | None = None, license_name: str = "unknown") -> dict[str, Any]:
    return {
        "kind": kind,
        "identifier": identifier,
        "revision": revision,
        "license": license_name,
        "raw_source_sha256": None,
    }


def _manifest_sources(cfg: dict, source_paths: dict[str, Path]) -> list[dict[str, Any]]:
    crawl = cfg.get("crawl", {}) or {}
    dataset_path = source_paths.get("dataset_groups")
    if dataset_path and dataset_path.is_file():
        groups = list((yaml.safe_load(dataset_path.read_text(encoding="utf-8")) or {}).get("dataset_groups", []))
    else:
        groups = [{"id": "default", "sources": crawl.get("sources", {})}]

    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    global_web = crawl.get("web", {}) or {}
    seed_path = source_paths.get("seed_urls")
    global_seeds = []
    if seed_path and seed_path.is_file():
        global_seeds = [
            line.strip()
            for line in seed_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    for group in groups:
        group_id = str(group.get("id", "default"))
        enabled = group.get("sources", crawl.get("sources", {})) or {}
        for kind in SOURCE_KINDS:
            if not bool(enabled.get(kind, kind != "google")):
                continue
            section = group.get(kind, {}) or {}
            if kind == "web":
                seeds = section.get("seed_urls") or global_web.get("seed_urls") or global_seeds
                identifiers = [str(url) for url in seeds]
                if not identifiers:
                    identifiers = [f"group:{group_id}:web"]
            elif kind == "github":
                identifiers = [f"group:{group_id}:github"]
            elif kind == "arxiv":
                identifiers = [f"group:{group_id}:arxiv"]
            elif kind == "huggingface":
                datasets = section.get("datasets", []) or []
                identifiers = [
                    f"{item.get('repo')}:{item.get('config', '')}:{item.get('split', 'train')}"
                    for item in datasets
                    if isinstance(item, dict) and item.get("repo")
                ]
                if not identifiers:
                    identifiers = [f"group:{group_id}:huggingface"]
            else:
                queries = section.get("queries", []) or []
                identifiers = [str(query) for query in queries]
                if not identifiers:
                    identifiers = [f"group:{group_id}:google"]
            for identifier in identifiers:
                key = (kind, identifier)
                if key not in seen:
                    seen.add(key)
                    sources.append(_source_entry(kind, identifier))
    return sources


def _write_source_manifest(
    path: Path,
    cfg: dict,
    source_paths: dict[str, Path],
    retrieval_started_at: str | None = None,
    retrieval_completed_at: str | None = None,
) -> None:
    started = retrieval_started_at or datetime.now(timezone.utc).isoformat()
    files = {
        name: {"path": str(value.relative_to(PROJECT_ROOT)), "sha256": _file_hash(value)}
        for name, value in source_paths.items()
    }
    manifest = {
        "schema": 1,
        "retrieval_started_at": started,
        "retrieval_completed_at": retrieval_completed_at,
        "source_definition_files": files,
        "sources": _manifest_sources(cfg, source_paths),
        "rights_note": "License and usage terms must be verified before distribution; unknown values are intentional.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_manifest_is_valid(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"schema", "retrieval_started_at", "retrieval_completed_at", "sources", "rights_note"}
        if not isinstance(data, dict) or not required <= set(data):
            return False
        if int(data["schema"]) != 1 or not data["retrieval_started_at"] or not data["retrieval_completed_at"]:
            return False
        if not isinstance(data["sources"], list) or not data["sources"]:
            return False
        for source in data["sources"]:
            if not isinstance(source, dict) or not REQUIRED_SOURCE_FIELDS <= set(source):
                return False
            digest = source["raw_source_sha256"]
            if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower())):
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False


class Pipeline:
    def __init__(self, config_path: str = "config/pipeline_config.yaml", dataset_id: int | None = None, resume: bool | None = None):
        requested = Path(config_path)
        if not requested.is_absolute():
            requested = PROJECT_ROOT / requested
        self._cfg_path = requested.resolve()
        self._project_root = PROJECT_ROOT
        if not self._cfg_path.is_file():
            raise FileNotFoundError(f"Pipeline config not found: {self._cfg_path}")
        self._config_sha256 = sha256_file(self._cfg_path)
        self.cfg = _load_config(self._cfg_path)
        self.cfg["_project_root"] = str(PROJECT_ROOT)
        self.cfg["_pipeline_config_path"] = str(self._cfg_path)
        validate_config(self.cfg)
        self.dataset_id = dataset_id
        configured_out = Path(self.cfg["pipeline"].get("output_dir", "output"))
        configured_scratch = Path(self.cfg["pipeline"].get("scratch_dir", "scratch"))
        if dataset_id is not None:
            self._dataset_root = PROJECT_ROOT / "datasets" / f"dataset_{dataset_id:03d}"
            if not self._dataset_root.is_dir():
                raise FileNotFoundError(f"Dataset session does not exist: {self._dataset_root}")
            self._out = self._dataset_root / "output"
            self._scratch = self._dataset_root / "scratch"
        else:
            self._dataset_root = None
            self._out = (PROJECT_ROOT / configured_out).resolve()
            self._scratch = (PROJECT_ROOT / configured_scratch).resolve()
        self._out.mkdir(parents=True, exist_ok=True)
        self._scratch.mkdir(parents=True, exist_ok=True)
        self.cfg["pipeline"]["output_dir"] = str(self._out)
        self.cfg["pipeline"]["scratch_dir"] = str(self._scratch)
        self.cfg.setdefault("tokenizer", {})["output_path"] = str(self._out / "tokenizer")
        self.cfg.setdefault("shard", {})["output_dir"] = str(self._out / "shards")
        self.cfg.setdefault("train", {})["shard_dir"] = str(self._out / "shards")
        self.cfg.setdefault("export", {})["llamacpp_dir"] = str(PROJECT_ROOT / self.cfg.get("export", {}).get("llamacpp_dir", "llama.cpp"))
        self.cfg["_pipeline_config_sha256"] = self._config_sha256
        self._resume = bool(self.cfg["pipeline"].get("resume", True)) if resume is None else bool(resume)
        self.cfg.setdefault("train", {})["resume"] = self._resume
        self._weights_path = PROJECT_ROOT / self.cfg.get("crawl", {}).get("source_weights_file", "config/source_weights.yaml")
        self._dataset_groups_path = PROJECT_ROOT / self.cfg.get("crawl", {}).get("dataset_groups_file", "config/dataset_groups.yaml")
        self._clean_config_path = PROJECT_ROOT / self.cfg.get("clean", {}).get("config_file", "config/cleaner_config.yaml")
        self._source_definition_paths = _source_definition_paths(self.cfg, PROJECT_ROOT)
        self._source_definition_hashes = {name: _file_hash(path) for name, path in self._source_definition_paths.items()}
        self._source_manifest_path = self._out.parent / "source_manifest.json"
        self._weights = SourceWeightLookup(str(self._weights_path))
        self._signals = DomainSignalTracker(self._weights.signal_gate_config())
        _setup_logging(self._out, str(self.cfg["pipeline"].get("log_level", "INFO")))
        log.info("Pipeline '%s' initialized | config=%s", self.cfg["pipeline"].get("name", "pipeline"), self._cfg_path)

    def _provenance(self, stage: str, input_path: Path | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema": 2,
            "stage": stage,
            "pipeline_config_sha256": self._config_sha256,
            "source_definition_sha256": _hash_value(self._source_definition_hashes),
            "implementation_sha256": _implementation_sha256(stage),
        }
        if input_path is not None:
            data["input_sha256"] = sha256_file(input_path)
        if extra:
            data.update(extra)
        return data

    def _should_skip(self, path: Path, stage: str, provenance: dict[str, Any]) -> bool:
        if self._resume and artifact_valid(path, expected_provenance=provenance):
            log.info("[%s] Verified artifact integrity and provenance, skipping: %s", stage, path)
            return True
        if path.exists() and self._resume:
            log.warning("[%s] Existing artifact is stale, unverified, or corrupt; rebuilding: %s", stage, path)
        return False

    def _load_dataset_groups(self) -> list[dict]:
        if not self._dataset_groups_path.exists():
            return [{"id": "default", "name": "default", "sources": self.cfg.get("crawl", {}).get("sources", {})}]
        return list((yaml.safe_load(self._dataset_groups_path.read_text(encoding="utf-8")) or {}).get("dataset_groups", []))

    def _session_group(self) -> dict | None:
        if self.dataset_id is None:
            return None
        meta_path = self._dataset_root / "dataset.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing dataset metadata: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        gid = meta.get("group_id")
        for group in self._load_dataset_groups():
            if group.get("id") == gid:
                return group
        if meta.get("group_config"):
            return meta["group_config"]
        raise ValueError(f"Dataset {self.dataset_id} references unknown group '{gid}'")

    def stage_crawl(self, only_group: str | None = None) -> Path:
        cfg = dict(self.cfg.get("crawl", {}))
        groups = self._load_dataset_groups()
        if self.dataset_id is not None:
            group = self._session_group()
            groups = [group] if group else []
        if only_group:
            groups = [g for g in groups if g.get("id") == only_group]
            if not groups:
                raise ValueError(f"Unknown dataset group id: {only_group}")
        out = self._scratch / (f"01_crawled__{only_group}.jsonl" if self.dataset_id is None and only_group else "01_crawled.jsonl")
        provenance = self._provenance(
            "crawl",
            extra={
                "source_weights_sha256": _file_hash(self._weights_path),
                "dataset_groups_sha256": _file_hash(self._dataset_groups_path),
                "dataset_group": only_group,
            },
        )
        if self._should_skip(out, "crawl", provenance) and _source_manifest_is_valid(self._source_manifest_path):
            return out

        retrieval_started = datetime.now(timezone.utc).isoformat()
        _write_source_manifest(
            self._source_manifest_path,
            self.cfg,
            self._source_definition_paths,
            retrieval_started_at=retrieval_started,
            retrieval_completed_at=None,
        )

        def stream() -> Iterator[Document]:
            crawler_specs = (
                ("web", "pipeline.crawler.web_crawler", "WebCrawler", True),
                ("github", "pipeline.crawler.github_crawler", "GitHubCrawler", True),
                ("arxiv", "pipeline.crawler.arxiv_crawler", "ArxivCrawler", True),
                ("huggingface", "pipeline.crawler.huggingface_crawler", "HuggingFaceCrawler", True),
                ("google", "pipeline.crawler.google_crawler", "GoogleCrawler", False),
            )
            for group in groups:
                merged = dict(cfg)
                for key in ("web", "github", "arxiv", "huggingface", "google"):
                    merged[key] = {**cfg.get(key, {}), **group.get(key, {})}
                merged["sources"] = group.get("sources", cfg.get("sources", {}))
                gid = group.get("id", "default")
                for source, module, klass, default_enabled in crawler_specs:
                    if not bool(merged.get("sources", {}).get(source, default_enabled)):
                        continue
                    crawler = _load_class(module, klass)(merged, self._weights, self._signals)
                    for doc in crawler.crawl():
                        doc.meta["dataset_group"] = gid
                        yield doc

        count = atomic_jsonl_write(out, lambda: (doc.to_jsonl() for doc in stream()))
        if count == 0:
            raise RuntimeError(f"Crawl produced no documents: {out}")
        _write_source_manifest(
            self._source_manifest_path,
            self.cfg,
            self._source_definition_paths,
            retrieval_started_at=retrieval_started,
            retrieval_completed_at=datetime.now(timezone.utc).isoformat(),
        )
        write_manifest(out, kind="crawl", rows=count, provenance=provenance)
        log.info("Wrote %d docs → %s", count, out)
        return out

    def stage_clean(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "02_cleaned.jsonl")
        provenance = self._provenance("clean", in_path, {"clean_config_sha256": _file_hash(self._clean_config_path)})
        if self._should_skip(out, "clean", provenance):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Clean input failed integrity validation: {in_path}")
        cleaner = _load_class("pipeline.cleaner.cleaner", "Cleaner")(str(self._clean_config_path))
        def cleaned() -> Iterator[Document]:
            for doc in _jsonl_read(in_path):
                result = cleaner.clean(doc.text, doc_id=doc.doc_id)
                if not result.kept:
                    continue
                doc.text = result.text
                doc.clean_action = result.action
                doc.clean_score = result.score
                doc.word_count = len(doc.text.split())
                doc.char_count = len(doc.text)
                yield doc
        _jsonl_write(cleaned(), out, kind="clean", provenance=provenance)
        return out

    def stage_embed_dedup(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "03_deduped.jsonl")
        dedup_cfg = self.cfg.get("embed_dedup", {})
        provenance = self._provenance("dedup", in_path, {"dedup_config_sha256": _hash_value(dedup_cfg)})
        if self._should_skip(out, "dedup", provenance):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Dedup input failed integrity validation: {in_path}")
        deduper = _load_class("pipeline.embedder.semantic_dedup", "SemanticDeduplicator")(dedup_cfg)
        buffer_size = int(dedup_cfg.get("buffer_size", 10000))
        def stream() -> Iterator[Document]:
            seen: set[str] = set()
            def unique_docs() -> Iterator[Document]:
                for doc in _jsonl_read(in_path):
                    key = hashlib.sha256(" ".join(doc.text.lower().split()).encode("utf-8", errors="replace")).hexdigest()
                    if key in seen:
                        continue
                    seen.add(key)
                    yield doc
            yield from deduper.stream(unique_docs(), buffer_size=buffer_size)
        _jsonl_write(stream(), out, kind="dedup", provenance=provenance)
        return out

    def stage_weight(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "04_weighted.jsonl")
        weight_cfg = self.cfg.get("weight", {})
        weights_path = PROJECT_ROOT / weight_cfg.get("config_file", "config/source_weights.yaml")
        provenance = self._provenance("weight", in_path, {"weight_config_sha256": _hash_value(weight_cfg), "source_weights_sha256": _file_hash(weights_path)})
        if self._should_skip(out, "weight", provenance):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Weight input failed integrity validation: {in_path}")
        weighter = _load_class("pipeline.weighter.weighter", "DomainWeighter")(str(weights_path), strategy=weight_cfg.get("strategy", "upsample"))
        _jsonl_write(weighter.apply(_jsonl_read(in_path)), out, kind="weight", provenance=provenance)
        return out

    def stage_tokenize(self, corpus_path: Path):
        tok_cfg = self.cfg.get("tokenizer", {})
        trainer = _load_class("pipeline.tokenizer.train_tokenizer", "BPETokenizerTrainer")(tok_cfg)
        marker = Path(tok_cfg["output_path"]) / "tokenizer.json"
        provenance = self._provenance("tokenize", corpus_path, {"tokenizer_config_sha256": _hash_value(tok_cfg)})
        if self._should_skip(marker, "tokenize", provenance):
            return trainer.load()
        if not artifact_valid(corpus_path):
            raise RuntimeError(f"Tokenizer input failed integrity validation: {corpus_path}")
        tokenizer = trainer.train(corpus_path)
        write_manifest(marker, kind="tokenizer", provenance=provenance, extra={"vocab_size": tokenizer.get_vocab_size()})
        return tokenizer

    def stage_shard(self, corpus_path: Path, tokenizer) -> Path:
        Writer = _load_class("pipeline.shardwriter.shard_writer", "ShardWriter")
        shard_cfg = self.cfg["shard"]
        shard_dir = Path(shard_cfg["output_dir"])
        marker = shard_dir / "shards.manifest.json"
        tok_cfg = self.cfg.get("tokenizer", {})
        tokenizer_path = Path(tok_cfg["output_path"]) / "tokenizer.json" if tok_cfg.get("output_path") else None
        provenance = self._provenance("shard", corpus_path, {"shard_config_sha256": _hash_value(shard_cfg), "tokenizer_sha256": _file_hash(tokenizer_path), "tokenizer_vocab_size": tokenizer.get_vocab_size()})
        if self._resume and marker.exists():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                files = data.get("files", [])
                valid = data.get("provenance") == provenance and bool(files)
                if valid:
                    for item in files:
                        shard_path = shard_dir / item["name"]
                        if not shard_path.is_file() or shard_path.stat().st_size != int(item["size"]) or not item.get("sha256") or sha256_file(shard_path) != item["sha256"]:
                            valid = False
                            break
                if valid:
                    log.info("[shard] Verified %d shards, hashes, and provenance, skipping", len(files))
                    return shard_dir
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                log.warning("[shard] Invalid shard manifest; rebuilding")
        shard_dir.mkdir(parents=True, exist_ok=True)
        for old in shard_dir.glob("shard_*.bin"):
            old.unlink(missing_ok=True)
        Writer(shard_cfg, tokenizer).write(corpus_path)
        paths = sorted(shard_dir.glob("shard_*.bin"))
        if not paths:
            raise RuntimeError("Shard stage produced no shard files")
        marker.write_text(json.dumps({"schema": 4, "files": [{"name": p.name, "size": p.stat().st_size, "sha256": sha256_file(p)} for p in paths], "source": str(corpus_path.resolve()), "source_sha256": sha256_file(corpus_path), "provenance": provenance, "sequence_length": int(shard_cfg.get("sequence_length", 1024)), "tokenizer_vocab_size": tokenizer.get_vocab_size()}, separators=(",", ":")) + "\n", encoding="utf-8")
        return shard_dir

    def stage_train(self) -> Path:
        import torch
        train_cfg = self.cfg.get("train", {})
        if not torch.cuda.is_available() and not bool(train_cfg.get("allow_cpu_training", False)):
            raise RuntimeError("CUDA is unavailable and allow_cpu_training=false; refusing accidental CPU pretraining.")
        self.cfg["_pipeline_config_sha256"] = self._config_sha256
        Trainer = _load_class("pipeline.trainer.train", "Trainer")
        Trainer(self.cfg).run()
        ckpt_dir = self._out / "checkpoints"
        candidates = sorted(ckpt_dir.glob("ckpt_best_*.pt")) or (sorted(ckpt_dir.glob("ckpt_final_*.pt")) if ckpt_dir.exists() else [])
        if not candidates:
            raise RuntimeError(f"Training completed without a checkpoint in {ckpt_dir}")
        return candidates[-1]

    def stage_export(self):
        exporter = _load_class("scripts.export_gguf", "export_checkpoint")
        exp = self.cfg.get("export", {})
        exporter(output_dir=self._out, llamacpp_dir=PROJECT_ROOT / exp.get("llamacpp_dir", "llama.cpp"), quant=str(exp.get("quant", "Q4_K_M")).upper(), model_name=exp.get("model_name", "model"))

    def run(self, stages: str = "all", dataset_group: str | None = None):
        stage_names = ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]
        if stages == "all":
            configured = self.cfg.get("stages", {}) or {}
            requested = [stage for stage in stage_names if bool(configured.get(stage, configured.get("semantic_dedup", False) if stage == "dedup" else False))]
        else:
            requested = [s.strip() for s in stages.split(",") if s.strip()]
        unknown = [s for s in requested if s not in stage_names]
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}")
        if not requested:
            raise ValueError("No enabled pipeline stages are configured")
        artifacts: dict[str, Any] = {}
        if "crawl" in requested:
            artifacts["crawl"] = self.stage_crawl(dataset_group)
        if "clean" in requested:
            artifacts["clean"] = self.stage_clean(artifacts.get("crawl", self._scratch / "01_crawled.jsonl"))
        if "dedup" in requested:
            artifacts["dedup"] = self.stage_embed_dedup(artifacts.get("clean", self._scratch / "02_cleaned.jsonl"))
        if "weight" in requested:
            artifacts["weight"] = self.stage_weight(artifacts.get("dedup", self._scratch / "03_deduped.jsonl"))
        if "tokenize" in requested:
            artifacts["tokenizer"] = self.stage_tokenize(artifacts.get("weight", self._scratch / "04_weighted.jsonl"))
        if "shard" in requested:
            artifacts["shard"] = self.stage_shard(artifacts.get("weight", self._scratch / "04_weighted.jsonl"), artifacts.get("tokenizer") or self.stage_tokenize(artifacts.get("weight", self._scratch / "04_weighted.jsonl")))
        if "train" in requested:
            artifacts["train"] = self.stage_train()
        if "export" in requested:
            artifacts["export"] = self.stage_export()
        log.info("Pipeline completed stages=%s", requested)
        return artifacts
