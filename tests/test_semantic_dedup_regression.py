import numpy as np
import pytest

import pipeline.embedder.semantic_dedup as mod
from pipeline.embedder.semantic_dedup import SemanticDeduplicator
from pipeline.types import Document


def doc(i, text, weight=1.0):
    return Document(
        doc_id=str(i),
        url=f"https://example.com/{i}",
        text=text,
        final_weight=weight,
    )


def test_run_empty_input(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)

    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    assert deduper.run([]) == []


def test_fallback_similarity_identical_text():
    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    assert deduper._fallback_similarity(
        "alpha beta gamma",
        "alpha beta gamma",
    ) == pytest.approx(1.0)


def test_fallback_similarity_disjoint_text():
    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    assert deduper._fallback_similarity(
        "alpha beta gamma",
        "delta epsilon zeta",
    ) == pytest.approx(0.0)


def test_fallback_similarity_empty_text():
    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    assert deduper._fallback_similarity("", "") == 0.0
    assert deduper._fallback_similarity("alpha", "") == 0.0


def test_unknown_mode_falls_back_to_supported_behavior(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)

    deduper = SemanticDeduplicator(
        {
            "mode": "unexpected",
            "similarity_threshold": 0.8,
        }
    )

    docs = [
        doc(1, "alpha beta gamma", 1.0),
        doc(2, "alpha beta gamma", 2.0),
    ]

    assert [item.doc_id for item in deduper.run(docs)] == ["2"]


def test_embedding_mode_requires_sentence_transformers(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)

    deduper = SemanticDeduplicator(
        {
            "mode": "embedding",
            "similarity_threshold": 0.8,
        }
    )

    with pytest.raises(RuntimeError, match="sentence-transformers"):
        deduper.run([doc(1, "alpha beta gamma")])


def test_embedding_run_uses_model_embeddings(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", True)
    monkeypatch.setattr(mod, "FAISS_AVAILABLE", False)

    deduper = SemanticDeduplicator(
        {
            "mode": "embedding",
            "similarity_threshold": 0.8,
        }
    )

    vectors = {
        "alpha beta gamma": np.array([1.0, 0.0], dtype=np.float32),
        "alpha beta delta": np.array([0.99, 0.1], dtype=np.float32),
        "completely unrelated": np.array([0.0, 1.0], dtype=np.float32),
    }

    monkeypatch.setattr(deduper, "_load_model", lambda: None)
    monkeypatch.setattr(
        deduper,
        "_embed",
        lambda texts: np.asarray(
            [vectors[text] for text in texts],
            dtype=np.float32,
        ),
    )

    docs = [
        doc(1, "alpha beta gamma", 1.0),
        doc(2, "alpha beta delta", 2.0),
        doc(3, "completely unrelated", 1.0),
    ]

    result = deduper.run(docs)

    assert [item.doc_id for item in result] == ["2", "3"]


def test_stream_rejects_invalid_buffer_size(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)

    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    with pytest.raises(ValueError, match="buffer_size"):
        list(deduper.stream(iter([doc(1, "alpha")]), buffer_size=0))


def test_stream_flushes_final_partial_buffer(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)

    deduper = SemanticDeduplicator({"similarity_threshold": 0.8})

    docs = iter(
        [
            doc(1, "alpha beta gamma", 1.0),
            doc(2, "totally different material", 1.0),
            doc(3, "another unrelated document", 1.0),
        ]
    )

    result = list(deduper.stream(docs, buffer_size=2))

    assert len(result) == 3


def test_embedding_stream_with_faiss(monkeypatch):
    monkeypatch.setattr(mod, "ST_AVAILABLE", True)
    monkeypatch.setattr(mod, "FAISS_AVAILABLE", True)

    deduper = SemanticDeduplicator(
        {
            "mode": "embedding",
            "similarity_threshold": 0.8,
        }
    )

    vectors = {
        "alpha": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "alpha similar": np.array([0.99, 0.1, 0.0], dtype=np.float32),
        "different": np.array([0.0, 0.0, 1.0], dtype=np.float32),
    }

    monkeypatch.setattr(deduper, "_load_model", lambda: None)
    monkeypatch.setattr(
        deduper,
        "_embed",
        lambda texts: np.asarray(
            [vectors[text] for text in texts],
            dtype=np.float32,
        ),
    )

    docs = iter(
        [
            doc(1, "alpha", 1.0),
            doc(2, "alpha similar", 2.0),
            doc(3, "different", 1.0),
        ]
    )

    result = list(deduper.stream(docs, buffer_size=1))

    assert [item.doc_id for item in result] == ["2", "3"]
