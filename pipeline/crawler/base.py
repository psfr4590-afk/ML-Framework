"""Abstract base class for all crawlers."""
from __future__ import annotations

import abc
import hashlib
import json
import logging
from pathlib import Path
from typing import Iterator

import yaml

from pipeline.dataset_contract import evaluate_document
from pipeline.types import Document

log = logging.getLogger("crawler.base")


class BaseCrawler(abc.ABC):
    """Every crawler yields Document objects with deterministic retrieval identity."""

    def __init__(self, cfg: dict, weight_lookup, signal_tracker):
        self.cfg = cfg
        self.weight_lookup = weight_lookup
        self.signal_tracker = signal_tracker
        self.stats = {"fetched": 0, "skipped": 0, "errors": 0, "abandoned_domains": 0, "excluded": 0, "quality_rejected": 0}
        self.project_root = Path(str(cfg.get("_project_root", Path(__file__).resolve().parents[2]))).resolve()
        self.dataset_group = str(cfg.get("dataset_group", "")).strip()
        self.exclusions = self._resolve_exclusions()

    def _resolve_exclusions(self) -> list[str]:
        """Resolve the active profile without trusting an unbound caller-provided tag list."""
        profiles_path = self.project_root / "config" / "dataset_profiles.yaml"
        groups_path = self.project_root / "config" / "dataset_groups.yaml"
        try:
            profiles = yaml.safe_load(profiles_path.read_text(encoding="utf-8")) or {}
            groups = yaml.safe_load(groups_path.read_text(encoding="utf-8")) or {}
            if not self.dataset_group:
                candidates = []
                for group in groups.get("dataset_groups", []):
                    if all(self.cfg.get(kind, {}) == group.get(kind, {}) for kind in ("web", "github", "arxiv", "huggingface", "google") if kind in group):
                        candidates.append(str(group.get("id", "")))
                if len(candidates) == 1:
                    self.dataset_group = candidates[0]
            for profile in profiles.get("dataset_profiles", []):
                if str(profile.get("group_id", "")) == self.dataset_group:
                    return [str(tag) for tag in profile.get("exclusions", [])]
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            log.warning("Dataset profile policy could not be loaded: %s", exc)
        return []

    @abc.abstractmethod
    def crawl(self) -> Iterator[Document]:
        ...

    @staticmethod
    def _record_retrieval_identity(doc: Document) -> Document:
        """Bind the emitted source record to the exact canonical bytes consumed downstream."""
        canonical = json.dumps(
            doc.to_jsonl(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        doc.meta["retrieval_provenance"] = {
            "identity_type": "canonical_record",
            "record_sha256": hashlib.sha256(canonical).hexdigest(),
        }
        return doc

    def _apply_weights(self, doc: Document) -> Document | None:
        dw, category = self.weight_lookup.domain_weight(doc.domain)
        ctw = self.weight_lookup.content_type_weight(doc.content_type)
        qs = self.weight_lookup.quality_score(doc.text)
        doc.domain_weight = dw
        doc.content_type_weight = ctw
        doc.quality_score = qs
        if doc.content_type == "source_code" and doc.code_language:
            ctw *= self.weight_lookup.code_language_weight(doc.code_language)
        doc.content_type_weight = ctw
        doc.final_weight = dw * ctw * qs
        if not doc.meta.get("category"):
            doc.meta["category"] = category

        keep, matches, quality = evaluate_document(self.project_root, doc, self.exclusions)
        doc.meta["dataset_group"] = self.dataset_group or doc.meta.get("dataset_group")
        doc.meta["quality_gate"] = {
            "score": quality,
            "minimum": 0.35,
            "passed": keep or not matches,
        }
        if matches:
            doc.meta["exclusion_matches"] = matches
            self.stats["excluded"] += 1
            return None
        if not keep:
            self.stats["quality_rejected"] += 1
            return None
        return self._record_retrieval_identity(doc)

    def print_stats(self):
        s = self.stats
        log.info(
            f"{self.__class__.__name__} | fetched={s['fetched']} "
            f"skipped={s['skipped']} errors={s['errors']} "
            f"excluded={s['excluded']} quality_rejected={s['quality_rejected']} "
            f"abandoned_domains={s['abandoned_domains']}"
        )
