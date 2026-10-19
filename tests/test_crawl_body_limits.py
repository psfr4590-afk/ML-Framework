"""Offline contract tests for the crawler's bounded body reader.

Extract the real helper so the tests do not require optional content parsers.
These do not replace HTTP transport or full crawler integration tests.
"""
import ast
from pathlib import Path

import pytest


@pytest.fixture
def read_body():
    path = Path(__file__).resolve().parents[1] / "pipeline/crawler/web_crawler.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    crawler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "WebCrawler")
    method = next(node for node in crawler.body if isinstance(node, ast.FunctionDef) and node.name == "_read_bounded_body")
    method.decorator_list = []
    module = ast.Module(body=[method], type_ignores=[])
    namespace = {}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["_read_bounded_body"]


class Response:
    def __init__(self, chunks, headers=None):
        self.chunks = chunks
        self.headers = headers or {}
        self.consumed = 0

    def iter_content(self, chunk_size):
        assert chunk_size > 0
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk


def test_body_at_exact_limit(read_body):
    assert read_body(Response([b"ab", b"cd"]), 4) == b"abcd"


def test_empty_chunks_are_ignored(read_body):
    assert read_body(Response([b"", b"ab", b""]), 2) == b"ab"


def test_content_length_rejects_before_consuming_body(read_body):
    response = Response([b"body"], {"Content-Length": "5"})
    with pytest.raises(ValueError):
        read_body(response, 4)
    assert response.consumed == 0


def test_missing_length_still_enforces_limit(read_body):
    response = Response([b"12345", b"unread"])
    with pytest.raises(ValueError):
        read_body(response, 4)
    assert response.consumed == 1


def test_misleading_length_still_enforces_limit(read_body):
    response = Response([b"12345"], {"Content-Length": "1"})
    with pytest.raises(ValueError):
        read_body(response, 4)


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_limit_rejected(read_body, limit):
    with pytest.raises(ValueError):
        read_body(Response([]), limit)


def test_invalid_length_header_does_not_disable_byte_count(read_body):
    with pytest.raises(ValueError):
        read_body(Response([b"12345"], {"Content-Length": "invalid"}), 4)
