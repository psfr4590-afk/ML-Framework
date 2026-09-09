"""Configurable quality filter for pretraining text.

The filter is intentionally independent from the pipeline orchestrator so it
can be used by callers that need to validate or transform text before it enters
the canonical stage chain.

Processing order:

    HTML strip -> Unicode normalization -> length gate -> exact dedup
    -> refusal/restriction scoring -> keep/drop/flag/redact
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

log = logging.getLogger("cleaner")


class Action(str, Enum):
    DROP = "drop"
    FLAG = "flag"
    REDACT = "redact"


@dataclass
class PatternGroup:
    name: str
    enabled: bool
    weight: float
    patterns: list[re.Pattern]


@dataclass
class CleanerConfig:
    action: Action
    score_threshold: float
    min_doc_length: int
    max_doc_length: int
    log_enabled: bool
    log_level: str
    log_file: str
    log_matched_text: bool
    log_doc_preview: int
    html_enabled: bool
    html_parser: str
    unicode_enabled: bool
    unicode_form: str
    strip_control_chars: bool
    dedup_enabled: bool
    dedup_method: str
    refusal_enabled: bool
    pattern_groups: list[PatternGroup]
    instant_drop_enabled: bool
    instant_drop_patterns: list[re.Pattern]


def _compile(raw: list[str]) -> list[re.Pattern]:
    compiled: list[re.Pattern] = []
    for pattern in raw:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            log.warning("Bad regex %r: %s", pattern, exc)
    return compiled


def load_config(path: str | Path) -> CleanerConfig:
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    general = raw.get("general", {})
    logging_cfg = raw.get("logging", {})
    html = raw.get("html", {})
    unicode_cfg = raw.get("unicode", {})
    dedup = raw.get("dedup", {})
    refusal = raw.get("refusal_filter", {})

    groups: list[PatternGroup] = []
    for name, group_cfg in refusal.get("pattern_groups", {}).items():
        groups.append(
            PatternGroup(
                name=name,
                enabled=group_cfg.get("enabled", True),
                weight=float(group_cfg.get("weight", 1.0)),
                patterns=_compile(group_cfg.get("patterns", [])),
            )
        )

    instant_drop = refusal.get("instant_drop_patterns", {})

    return CleanerConfig(
        action=Action(general.get("action", "drop")),
        score_threshold=float(general.get("score_threshold", 0.12)),
        min_doc_length=int(general.get("min_doc_length", 80)),
        max_doc_length=int(general.get("max_doc_length", 2_000_000)),
        log_enabled=logging_cfg.get("enabled", True),
        log_level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("log_file", "output/logs/cleaner.log"),
        log_matched_text=logging_cfg.get("log_matched_text", True),
        log_doc_preview=int(logging_cfg.get("log_doc_preview", 120)),
        html_enabled=html.get("enabled", True),
        html_parser=html.get("parser", "lxml"),
        unicode_enabled=unicode_cfg.get("enabled", True),
        unicode_form=unicode_cfg.get("normalize_form", "NFKC"),
        strip_control_chars=unicode_cfg.get("strip_control_chars", True),
        dedup_enabled=dedup.get("enabled", True),
        dedup_method=dedup.get("method", "exact_hash"),
        refusal_enabled=refusal.get("enabled", True),
        pattern_groups=groups,
        instant_drop_enabled=instant_drop.get("enabled", True),
        instant_drop_patterns=_compile(instant_drop.get("patterns", [])),
    )


@dataclass
class CleanResult:
    kept: bool
    action: str
    text: str
    score: float = 0.0
    hits: list[dict] = field(default_factory=list)
    doc_id: str = ""


class Cleaner:
    """Stateful quality filter with hot-reloadable configuration."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.cfg = load_config(self.config_path)
        self._seen: set[str] = set()
        self._mtime = self.config_path.stat().st_mtime
        self.stats = {
            "total": 0,
            "kept": 0,
            "dropped_refusal": 0,
            "dropped_short": 0,
            "dropped_long": 0,
            "dropped_dedup": 0,
            "flagged": 0,
            "redacted": 0,
        }
        log.info(
            "Cleaner ready | action=%s threshold=%s",
            self.cfg.action,
            self.cfg.score_threshold,
        )

    def reload(self) -> None:
        self.cfg = load_config(self.config_path)
        self._mtime = self.config_path.stat().st_mtime
        log.info("Cleaner config reloaded")

    def _maybe_reload(self) -> None:
        try:
            mtime = self.config_path.stat().st_mtime
            if mtime != self._mtime:
                self.reload()
        except OSError:
            return

    def _strip_html(self, text: str) -> str:
        if not self.cfg.html_enabled:
            return text
        if BS4_AVAILABLE:
            soup = BeautifulSoup(text, self.cfg.html_parser)
            for tag in soup(
                ["script", "style", "nav", "footer", "aside", "header", "form", "noscript", "iframe"]
            ):
                tag.decompose()
            return soup.get_text(separator=" ")
        return re.sub(r"<[^>]+>", " ", text)

    def _normalize(self, text: str) -> str:
        if not self.cfg.unicode_enabled:
            return text
        text = unicodedata.normalize(self.cfg.unicode_form, text)
        if self.cfg.strip_control_chars:
            text = "".join(
                char
                for char in text
                if unicodedata.category(char) not in ("Cc", "Cf")
                or char in ("\n", "\t")
            )
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _is_duplicate(self, text: str) -> bool:
        if not self.cfg.dedup_enabled:
            return False
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        if digest in self._seen:
            return True
        self._seen.add(digest)
        return False

    def _score(self, text: str) -> tuple[float, list[dict]]:
        hits: list[dict] = []
        weighted = 0.0
        tokens = max(len(text.split()), 1)

        if self.cfg.instant_drop_enabled:
            for pattern in self.cfg.instant_drop_patterns:
                match = pattern.search(text)
                if match:
                    return 999.0, [
                        {
                            "group": "instant_drop",
                            "pattern": pattern.pattern,
                            "span": match.span(),
                            "matched": match.group(0)
                            if self.cfg.log_matched_text
                            else "",
                        }
                    ]

        for group in self.cfg.pattern_groups:
            if not group.enabled:
                continue
            for pattern in group.patterns:
                for match in pattern.finditer(text):
                    hits.append(
                        {
                            "group": group.name,
                            "pattern": pattern.pattern,
                            "span": match.span(),
                            "matched": match.group(0)
                            if self.cfg.log_matched_text
                            else "",
                        }
                    )
                    weighted += group.weight

        return weighted / tokens, hits

    def _redact(self, text: str, hits: list[dict]) -> str:
        chars = list(text)
        for hit in sorted(hits, key=lambda item: item["span"][0], reverse=True):
            start, end = hit["span"]
            chars[start:end] = list("[REMOVED]")
        return "".join(chars)

    def clean(self, text: str, doc_id: str = "") -> CleanResult:
        """Normalize and classify one document without raising for bad content."""
        self._maybe_reload()
        self.stats["total"] += 1
        cfg = self.cfg

        text = self._strip_html(text)
        text = self._normalize(text)

        if len(text) < cfg.min_doc_length:
            self.stats["dropped_short"] += 1
            return CleanResult(False, "too_short", "", doc_id=doc_id)

        if len(text) > cfg.max_doc_length:
            self.stats["dropped_long"] += 1
            return CleanResult(False, "too_long", "", doc_id=doc_id)

        if self._is_duplicate(text):
            self.stats["dropped_dedup"] += 1
            log.info("[%s] DROP duplicate", doc_id)
            return CleanResult(False, "duplicate", "", doc_id=doc_id)

        score, hits = self._score(text) if cfg.refusal_enabled else (0.0, [])

        if score >= cfg.score_threshold:
            if cfg.action == Action.DROP:
                self.stats["dropped_refusal"] += 1
                return CleanResult(False, "dropped", "", score, hits, doc_id)
            if cfg.action == Action.FLAG:
                self.stats["flagged"] += 1
                return CleanResult(True, "flagged", text, score, hits, doc_id)
            if cfg.action == Action.REDACT:
                self.stats["redacted"] += 1
                return CleanResult(
                    True,
                    "redacted",
                    self._redact(text, hits),
                    score,
                    hits,
                    doc_id,
                )

        self.stats["kept"] += 1
        return CleanResult(True, "kept", text, score, hits, doc_id)

    def print_stats(self) -> None:
        stats = self.stats
        total = max(stats["total"], 1)
        log.info(
            "Cleaner stats | total=%d kept=%d (%.1f%%) "
            "drop_refusal=%d drop_short=%d drop_long=%d "
            "drop_dedup=%d flagged=%d redacted=%d",
            stats["total"],
            stats["kept"],
            stats["kept"] / total * 100,
            stats["dropped_refusal"],
            stats["dropped_short"],
            stats["dropped_long"],
            stats["dropped_dedup"],
            stats["flagged"],
            stats["redacted"],
        )

    def reset_dedup(self) -> None:
        self._seen.clear()
