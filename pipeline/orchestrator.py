"""Pipeline orchestration for the Model Lab end-to-end training flow.

The orchestrator keeps stage boundaries explicit, verifies persisted artifacts
before resume, isolates dataset sessions, and avoids importing optional heavy
dependencies until the corresponding stage is actually requested.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import time
from pathlib import Path
from typing import Iterator

import yaml

from pipeline.config_validation import validate_config
from pipeline.integrity import artifact_valid, atomic_jsonl_write, sha256_file, write_manifest
from pipeline.types import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("orchestrator")


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
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _jsonl_write(docs: Iterator[Document], path: Path, kind: str = "jsonl") -> int:
    count = atomic_jsonl_write(path, (doc.to_jsonl() for doc in docs))
    write_manifest(path, kind=kind, rows=count)
    log.info("Wrote %d docs → %s", count, path)
    return count


def _jsonl_read(path: Path) -> Iterator[Document]:
    if not path.exists():
        raise FileNotFoundError(f"Required pipeline input does not exist: {path}")
    with open(path, "r", encoding="utf-8") as handle:
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
    """Load an optional stage provider only when that provider is enabled."""
    return getattr(importlib.import_module(module), name)


class Pipeline:
    def __init__(self, config_path: str = "config/pipeline_config.yaml", dataset_id: int | None = None):
        requested = Path(config_path)
        if not requested.is_absolute():
            requested = PROJECT_ROOT / requested
        self._cfg_path = requested.resolve()
        if not self._cfg_path.is_file():
            raise FileNotFoundError(f"Pipeline config not found: {self._cfg_path}")

        self.cfg = _load_config(self._cfg_path)
        self.cfg["_project_root"] = str(PROJECT_ROOT)
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

        _setup_logging(self._out, str(self.cfg["pipeline"].get("log_level", "INFO")))
        self._resume = bool(self.cfg["pipeline"].get("resume", True))
        log.info("Pipeline '%s' initialized | config=%s", self.cfg["pipeline"].get("name", "pipeline"), self._cfg_path)

    def _should_skip(self, path: Path, stage: str) -> bool:
        if self._resume and artifact_valid(path):
            log.info("[%s] Verified artifact exists, skipping: %s", stage, path)
            return True
        if path.exists() and self._resume:
            log.warning("[%s] Existing artifact is unverified or corrupt; rebuilding: %s", stage, path)
        return False

    def _load_dataset_groups(self) -> list[dict]:
        path = PROJECT_ROOT / self.cfg.get("crawl", {}).get("dataset_groups_file", "config/dataset_groups.yaml")
        if not path.exists():
            return [{"id": "default", "name": "default", "sources": self.cfg.get("crawl", {}).get("sources", {})}]
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return list(data.get("dataset_groups", []))

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

        out = self._scratch / "01_crawled.jsonl"
        if self.dataset_id is None and only_group:
            out = self._scratch / f"01_crawled__{only_group}.jsonl"
        if self._should_skip(out, "crawl"):
            return out

        def stream() -> Iterator[Document]:
            crawler_specs = (
                ("web", "pipeline.crawler.web_crawler", "WebCrawler", True),
                ("github", "pipeline.crawler.github_crawler", "GitHubCrawler", True),
                ("arxiv", "pipeline.crawler.arxiv_crawler", "ArxivCrawler", True),
                ("huggingface", "pipeline.crawler.huggingface_crawler", "HuggingFaceCrawler", False),
                ("google", "pipeline.crawler.google_crawler", "GoogleCrawler", False),
            )
            for group in groups:
                merged = dict(cfg)
                for key in ("web", "github", "arxiv", "huggingface", "google"):
                    merged[key] = {**cfg.get(key, {}), **group.get(key, {})}
                merged["sources"] = group.get("sources", cfg.get("sources", {}))
                gid = group.get("id", "default")
                log.info("Crawling dataset group '%s'", gid)
                for source, module, klass, default_enabled in crawler_specs:
                    enabled = bool(merged.get("sources", {}).get(source, default_enabled))
                    if not enabled:
                        continue
                    try:
                        cls = _load_class(module, klass)
                    except (ImportError, AttributeError) as exc:
                        raise RuntimeError(f"Crawler '{source}' is enabled but unavailable: {exc}") from exc
                    crawler = cls(merged, None, None) if source != "web" else cls(merged, None, None)
                    for doc in crawler.crawl():
                        doc.meta["dataset_group"] = gid
                        yield doc

        count = _jsonl_write(stream(), out, kind="crawl")
        if count == 0:
            raise RuntimeError(f"Crawl produced no documents: {out}")
        return out

    def stage_clean(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "02_cleaned.jsonl")
        if self._should_skip(out, "clean"):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Clean input failed integrity validation: {in_path}")
        Cleaner = _load_class("pipeline.cleaner.cleaner", "Cleaner")
        cleaner = Cleaner(str(PROJECT_ROOT / self.cfg.get("clean", {}).get("config_file", "config/cleaner_config.yaml")))

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

        _jsonl_write(cleaned(), out, kind="clean")
        return out

    def stage_embed_dedup(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "03_deduped.jsonl")
        if self._should_skip(out, "dedup"):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Dedup input failed integrity validation: {in_path}")
        Deduplicator = _load_class("pipeline.embedder.semantic_dedup", "SemanticDeduplicator")
        deduper = Deduplicator(self.cfg.get("embed_dedup", {}))
        buffer_size = int(self.cfg.get("embed_dedup", {}).get("buffer_size", 10000))

        def stream() -> Iterator[Document]:
            buf: list[Document] = []
            seen: set[str] = set()
            for doc in _jsonl_read(in_path):
                key = hashlib.sha256(" ".join(doc.text.lower().split()).encode("utf-8", errors="replace")).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                buf.append(doc)
                if len(buf) >= buffer_size:
                    yield from deduper.run(buf)
                    buf.clear()
            if buf:
                yield from deduper.run(buf)

        _jsonl_write(stream(), out, kind="dedup")
        return out

    def stage_weight(self, in_path: Path, out_path: Path | None = None) -> Path:
        out = out_path or (self._scratch / "04_weighted.jsonl")
        if self._should_skip(out, "weight"):
            return out
        if not artifact_valid(in_path):
            raise RuntimeError(f"Weight input failed integrity validation: {in_path}")
        Weighter = _load_class("pipeline.weighter.weighter", "DomainWeighter")
        weights_path = PROJECT_ROOT / self.cfg.get("weight", {}).get("config_file", "config/source_weights.yaml")
        strategy = self.cfg.get("weight", {}).get("strategy", "upsample")
        weighter = Weighter(str(weights_path), strategy=strategy)
        _jsonl_write(weighter.apply(_jsonl_read(in_path)), out, kind="weight")
        return out

    def stage_tokenize(self, corpus_path: Path):
        Trainer = _load_class("pipeline.tokenizer.train_tokenizer", "BPETokenizerTrainer")
        trainer = Trainer(self.cfg.get("tokenizer", {}))
        marker = Path(self.cfg["tokenizer"]["output_path"]) / "tokenizer.json"
        if self._should_skip(marker, "tokenize"):
            return trainer.load()
        if not artifact_valid(corpus_path):
            raise RuntimeError(f"Tokenizer input failed integrity validation: {corpus_path}")
        tokenizer = trainer.train(corpus_path)
        write_manifest(marker, kind="tokenizer", extra={"vocab_size": tokenizer.get_vocab_size()})
        return tokenizer

    def stage_shard(self, corpus_path: Path, tokenizer) -> Path:
        Writer = _load_class("pipeline.shardwriter.shard_writer", "ShardWriter")
        shard_dir = Path(self.cfg["shard"]["output_dir"])
        marker = shard_dir / "shards.manifest.json"
        if self._resume and marker.exists():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                files = data.get("files", [])
                if files and all(
                    (shard_dir / item["name"]).is_file()
                    and (shard_dir / item["name"]).stat().st_size == int(item["size"])
                    and sha256_file(shard_dir / item["name"]) == item["sha256"]
                    for item in files
                ):
                    log.info("[shard] Verified %d shards, skipping", len(files))
                    return shard_dir
            except (OSError, ValueError, TypeError, KeyError):
                log.warning("[shard] Invalid shard manifest; rebuilding")
        shard_dir.mkdir(parents=True, exist_ok=True)
        for old in shard_dir.glob("shard_*.bin"):
            old.unlink(missing_ok=True)
        Writer(self.cfg["shard"], tokenizer).write(corpus_path)
        paths = sorted(shard_dir.glob("shard_*.bin"))
        if not paths:
            raise RuntimeError("Shard stage produced no shard files")
        marker.write_text(json.dumps({
            "schema": 3,
            "files": [{"name": p.name, "size": p.stat().st_size, "sha256": sha256_file(p)} for p in paths],
            "source": str(corpus_path.resolve()),
            "source_sha256": sha256_file(corpus_path),
            "tokenizer_vocab_size": tokenizer.get_vocab_size(),
            "sequence_length": int(self.cfg["shard"].get("sequence_length", 1024)),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return shard_dir

    def stage_train(self) -> Path:
        import torch
        train_cfg = self.cfg.get("train", {})
        if not torch.cuda.is_available() and not bool(train_cfg.get("allow_cpu_training", False)):
            raise RuntimeError("CUDA is unavailable and allow_cpu_training=false; refusing accidental CPU pretraining")
        Trainer = _load_class("pipeline.trainer.train", "Trainer")
        Trainer(self.cfg).run()
        ckpt_dir = self._out / "checkpoints"
        candidates = sorted(ckpt_dir.glob("ckpt_best_*.pt")) or sorted(ckpt_dir.glob("ckpt_*.pt"))
        if not candidates:
            raise RuntimeError(f"Training completed without a checkpoint in {ckpt_dir}")
        return candidates[-1]

    def stage_export(self):
        exporter = _load_class("scripts.export_gguf", "export_checkpoint")
        exp = self.cfg.get("export", {})
        result = exporter(
            output_dir=self._out,
            llamacpp_dir=PROJECT_ROOT / exp.get("llamacpp_dir", "llama.cpp"),
            quant=str(exp.get("quant", "Q4_K_M")).upper(),
            model_name=exp.get("model_name", "pretrain-model"),
        )
        return Path(result["final_gguf"])

    def run(self, stages: str = "all", dataset_group: str | None = None):
        stage_names = ["crawl", "clean", "dedup", "weight", "tokenize", "shard", "train", "export"]
        requested = stage_names if stages == "all" else [s.strip() for s in stages.split(",") if s.strip()]
        unknown = [s for s in requested if s not in stage_names]
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}; valid stages: {stage_names}")
        if dataset_group and self.dataset_id is None and any(s in requested for s in ("train", "export")):
            raise RuntimeError("Training/export with dataset groups requires --dataset-id for isolated artifacts")

        suffix = "" if self.dataset_id is not None else (f"__{dataset_group}" if dataset_group else "")
        crawled = self._scratch / f"01_crawled{suffix}.jsonl"
        cleaned = self._scratch / f"02_cleaned{suffix}.jsonl"
        deduped = self._scratch / f"03_deduped{suffix}.jsonl"
        weighted = self._scratch / f"04_weighted{suffix}.jsonl"
        t0 = time.time()

        if "crawl" in requested:
            crawled = self.stage_crawl(dataset_group)
        if any(s in requested for s in ("clean", "dedup", "weight", "tokenize", "shard")) and not crawled.exists():
            raise RuntimeError(f"Missing crawl artifact: {crawled}")
        if "clean" in requested:
            cleaned = self.stage_clean(crawled, cleaned)
        if "dedup" in requested:
            dedup_source = cleaned if cleaned.exists() else crawled
            deduped = self.stage_embed_dedup(dedup_source, deduped)
        if "weight" in requested:
            weight_source = deduped if deduped.exists() else (cleaned if cleaned.exists() else crawled)
            weighted = self.stage_weight(weight_source, weighted)

        tokenizer = None
        if "tokenize" in requested:
            tok_source = weighted if weighted.exists() else (deduped if deduped.exists() else cleaned)
            tokenizer = self.stage_tokenize(tok_source)
        if "shard" in requested:
            if tokenizer is None:
                Trainer = _load_class("pipeline.tokenizer.train_tokenizer", "BPETokenizerTrainer")
                tokenizer = Trainer(self.cfg["tokenizer"]).load()
            shard_source = weighted if weighted.exists() else (deduped if deduped.exists() else cleaned)
            self.stage_shard(shard_source, tokenizer)
        if "train" in requested:
            self.stage_train()
        if "export" in requested:
            self.stage_export()

        log.info("Pipeline complete in %.1fs", time.time() - t0)


__all__ = ["Pipeline"]
