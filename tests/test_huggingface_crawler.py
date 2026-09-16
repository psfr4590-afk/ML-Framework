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
