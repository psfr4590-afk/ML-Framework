from __future__ import annotations

import json
from pathlib import Path

from scripts.export_cards import write_export_cards


def _manifest(path: Path, rows: int, stage: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    path.with_name(path.name + ".manifest.json").write_text(
        json.dumps({
            "schema": 2,
            "kind": stage,
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            "rows": rows,
            "provenance": {"pipeline_config_sha256": "config-sha"},
        }),
        encoding="utf-8",
    )


def test_write_export_cards_creates_both_cards_and_lineage(tmp_path, monkeypatch):
    output = tmp_path / "output"
    scratch = tmp_path / "scratch"
    for prefix, rows in (("01_crawled", 10), ("02_cleaned", 8), ("03_deduped", 7), ("04_weighted", 9)):
        _manifest(scratch / f"{prefix}.jsonl", rows, prefix.split("_", 1)[1])
    (output / "tokenizer").mkdir(parents=True)
    (output / "tokenizer" / "tokenizer.json").write_text("{}", encoding="utf-8")
    (output / "shards").mkdir(parents=True)
    (output / "shards" / "shards.manifest.json").write_text(
        json.dumps({"dtype": "uint16", "files": [{"name": "shard_00000_train.bin", "size": 20}]}),
        encoding="utf-8",
    )
    (tmp_path / "source_manifest.json").write_text(
        json.dumps({"schema": 1, "sources": [], "source_definition_files": {}, "retrieval_started_at": "test", "rights_note": "test"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.export_cards._git_commit", lambda: "git-sha")

    manifest = {
        "model_name": "test-model",
        "quantization": "F16",
        "checkpoint_step": 3,
        "final_gguf": str(output / "gguf" / "model-f16.gguf"),
        "final_gguf_sha256": "gguf-sha",
        "f16_gguf_sha256": "gguf-sha",
        "converter_version": "b10516@commit",
        "model_config": {"vocab_size": 32},
    }
    paths = write_export_cards(
        output,
        manifest,
        {"step": 3, "model_cfg": {"vocab_size": 32}, "train_cfg": {"seed": 42}, "provenance": {"shard_manifest_sha256": "shard-sha"}},
    )

    dataset_card = Path(paths["dataset_card"])
    model_card = Path(paths["model_card"])
    assert dataset_card.is_file()
    assert model_card.is_file()
    assert "Pipeline configuration SHA-256: `config-sha`" in dataset_card.read_text(encoding="utf-8")
    assert "Final GGUF SHA-256: `gguf-sha`" in model_card.read_text(encoding="utf-8")
    assert "Dataset card: `DATASET_CARD.md`" in model_card.read_text(encoding="utf-8")
