import pipeline.crawler.huggingface_crawler as huggingface_module
from pipeline.crawler.huggingface_crawler import HuggingFaceCrawler


def test_row_text_fields_preserves_labeled_reasoning_fields() -> None:
    row = {
        "question": "What is 2 + 2?",
        "context": {"contexts": ["Basic arithmetic"]},
        "answer": "4",
    }

    text = HuggingFaceCrawler._row_text_fields(row, ["question", "context", "answer"])

    assert "question: What is 2 + 2?" in text
    assert 'context: {"contexts": ["Basic arithmetic"]}' in text
    assert "answer: 4" in text


def test_row_text_fields_skips_missing_fields() -> None:
    row = {"question": "What is 2 + 2?"}

    text = HuggingFaceCrawler._row_text_fields(row, ["question", "context", "answer"])

    assert text == "question: What is 2 + 2?"


def test_crawl_records_retrieval_provenance_without_weight_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        huggingface_module,
        "load_dataset",
        lambda *args, **kwargs: [{"question": "What is 2 + 2?", "answer": "4"}],
    )
    crawler = HuggingFaceCrawler(
        {
            "huggingface": {
                "datasets": [
                    {
                        "repo": "example/dataset",
                        "revision": "0123456",
                        "split": "train",
                        "text_fields": ["question", "answer"],
                        "max_docs": 1,
                    }
                ]
            }
        },
        weight_lookup=None,
        signal_tracker=None,
    )

    doc = next(crawler.crawl())

    assert doc.meta["source_identity"]["revision"] == "0123456"
    assert doc.meta["retrieval_provenance"]["identity_type"] == "canonical_record"
    assert len(doc.meta["retrieval_provenance"]["record_sha256"]) == 64
