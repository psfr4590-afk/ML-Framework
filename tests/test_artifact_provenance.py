import json

from pipeline.integrity import artifact_valid, sha256_file, write_manifest


def test_artifact_valid_rejects_changed_provenance(tmp_path):
    path = tmp_path / "artifact.jsonl"
    path.write_text('{"id":1}\n', encoding="utf-8")
    write_manifest(path, kind="clean", provenance={"schema": 1, "input_sha256": "old"})

    assert artifact_valid(path)
    assert not artifact_valid(path, expected_provenance={"schema": 1, "input_sha256": "new"})


def test_artifact_valid_rejects_changed_source(tmp_path):
    source = tmp_path / "source.jsonl"
    artifact = tmp_path / "artifact.jsonl"
    source.write_text("old\n", encoding="utf-8")
    artifact.write_text("derived\n", encoding="utf-8")
    manifest = {
        "schema": 2,
        "kind": "clean",
        "path": str(artifact),
        "size": artifact.stat().st_size,
        "sha256": sha256_file(artifact),
        "source": str(source),
        "source_sha256": sha256_file(source),
    }
    artifact.with_name(artifact.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert artifact_valid(artifact)
    source.write_text("changed\n", encoding="utf-8")
    assert not artifact_valid(artifact)


def test_artifact_valid_rejects_unknown_manifest_schema(tmp_path):
    path = tmp_path / "artifact.jsonl"
    path.write_text("data\n", encoding="utf-8")
    manifest = {
        "schema": 999,
        "kind": "clean",
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert not artifact_valid(path)


def test_artifact_valid_rejects_missing_manifest_kind(tmp_path):
    path = tmp_path / "artifact.jsonl"
    path.write_text("data\n", encoding="utf-8")
    manifest = {
        "schema": 2,
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    path.with_name(path.name + ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert not artifact_valid(path)
