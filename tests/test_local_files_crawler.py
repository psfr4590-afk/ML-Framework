from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.config_validation import validate_config
from pipeline.crawler.local_files_crawler import LocalFilesCrawler


class _Weights:
    def domain_weight(self, _domain):
        return 1.0, "local"

    def content_type_weight(self, _content_type):
        return 1.0

    def quality_score(self, text):
        return 1.0 if text else 0.0


class _Signals:
    def record(self, *_args):
        return None


def _crawler(root: Path, **settings) -> LocalFilesCrawler:
    config = {
        "_project_root": str(root),
        "local_files": {"paths": [str(root)], **settings},
    }
    return LocalFilesCrawler(config, _Weights(), _Signals())


def test_local_files_crawler_reads_supported_text_and_records_provenance(tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("A useful local document about systems engineering.", encoding="utf-8")

    docs = list(_crawler(tmp_path).crawl())

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "local_files"
    assert doc.url == source.as_uri()
    assert doc.meta["source_mode"] == "local"
    assert doc.meta["local_path"] == str(source.resolve())
    assert len(doc.meta["file_sha256"]) == 64
    assert doc.text == source.read_text(encoding="utf-8")


def test_local_files_crawler_is_bounded_by_file_size_and_count(tmp_path):
    (tmp_path / "a.txt").write_text("first document", encoding="utf-8")
    (tmp_path / "b.txt").write_text("second document", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * 128, encoding="utf-8")

    docs = list(_crawler(tmp_path, max_files=2, max_file_bytes=64).crawl())

    assert len(docs) <= 2
    assert all(len(doc.text) <= 64 for doc in docs)


def test_local_files_crawler_ignores_unsupported_files(tmp_path):
    (tmp_path / "notes.txt").write_text("supported text document", encoding="utf-8")
    (tmp_path / "binary.exe").write_bytes(b"not a supported document")

    docs = list(_crawler(tmp_path).crawl())

    assert len(docs) == 1
    assert docs[0].url.endswith("notes.txt")


def test_local_files_crawler_reports_missing_paths_without_fabricating_documents(tmp_path):
    crawler = LocalFilesCrawler(
        {"_project_root": str(tmp_path), "local_files": {"paths": ["missing-folder"]}},
        _Weights(),
        _Signals(),
    )

    assert list(crawler.crawl()) == []
    assert crawler.stats["errors"] == 1


def test_config_validation_accepts_local_files_source_and_rejects_bad_limits(tmp_path):
    import yaml

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    cfg["crawl"]["sources"]["local_files"] = True
    cfg["crawl"]["local_files"] = {
        "paths": [str(tmp_path)],
        "recursive": True,
        "extensions": [".txt", ".md"],
        "max_files": 10,
        "max_file_bytes": 1024,
    }

    validate_config(cfg)

    cfg["crawl"]["local_files"]["max_files"] = 0
    with pytest.raises(ValueError, match="max_files"):
        validate_config(cfg)



def test_local_files_crawler_skips_oversized_file(tmp_path):
    (tmp_path / "small.txt").write_text("small useful document", encoding="utf-8")
    (tmp_path / "large.txt").write_text("x" * 128, encoding="utf-8")

    crawler = _crawler(tmp_path, max_file_bytes=64)
    docs = list(crawler.crawl())

    assert len(docs) == 1
    assert docs[0].url.endswith("small.txt")
    assert crawler.stats["skipped"] == 1


def test_config_validation_requires_paths_when_local_source_is_enabled(tmp_path):
    import yaml

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "config" / "pipeline_config.yaml").read_text(encoding="utf-8"))
    cfg["crawl"]["sources"]["local_files"] = True
    cfg["crawl"]["local_files"] = {"paths": []}

    with pytest.raises(ValueError, match="paths is required"):
        validate_config(cfg)
