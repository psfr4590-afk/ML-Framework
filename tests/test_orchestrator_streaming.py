from __future__ import annotations

import json
from pathlib import Path

from pipeline.orchestrator import _jsonl_write


class _Doc:
    def __init__(self, value: str):
        self.value = value

    def to_jsonl(self) -> str:
        return json.dumps({"value": self.value})


def test_jsonl_write_accepts_iterator_producer(tmp_path: Path):
    path = tmp_path / "docs.jsonl"
    docs = (_Doc(value) for value in ("alpha", "beta"))

    count = _jsonl_write(docs, path, kind="test")

    assert count == 2
    assert path.read_text(encoding="utf-8").splitlines() == [
        '{"value": "alpha"}',
        '{"value": "beta"}',
    ]
