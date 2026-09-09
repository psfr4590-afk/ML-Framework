from pipeline.embedder.semantic_dedup import SemanticDeduplicator
from pipeline.types import Document


def doc(i, text, weight):
    return Document(doc_id=str(i), url=f"https://example.com/{i}", text=text, final_weight=weight)


def test_fallback_stream_dedup_crosses_buffer_boundary(monkeypatch):
    import pipeline.embedder.semantic_dedup as mod
    monkeypatch.setattr(mod, "ST_AVAILABLE", False)
    d = SemanticDeduplicator({"similarity_threshold": 0.5})
    docs = iter([
        doc(1, "alpha beta gamma delta", 1.0),
        doc(2, "totally different corpus material", 1.0),
        doc(3, "alpha beta gamma delta", 2.0),
    ])
    out = list(d.stream(docs, buffer_size=1))
    assert [x.doc_id for x in out] == ["3", "2"]
