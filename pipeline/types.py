from __future__ import annotations

"""Shared data types for the pretrain pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    doc_id: str
    url: str
    text: str
    title: str = ""
    source: str = ""
    content_type: str = "unknown"
    word_count: int = 0
    char_count: int = 0
    final_weight: float = 1.0
    meta: dict[str, Any] = field(default_factory=dict)
    clean_action: str = ""
    clean_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.word_count:
            self.word_count = len(self.text.split())
        if not self.char_count:
            self.char_count = len(self.text)
