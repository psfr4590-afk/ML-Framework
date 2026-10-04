from __future__ import annotations

from pathlib import Path

import pytest

from command_center import security


def test_validate_import_source_accepts_relative_path(tmp_path, monkeypatch) -> None:
    root = tmp_path / "imports"
    root.mkdir()
    source = root / "nested" / "sample.txt"
    source.parent.mkdir()
    source.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(security, "IMPORT_ROOT", root)

    assert security.validate_import_source("nested/sample.txt") == source


@pytest.mark.parametrize(
    "candidate",
    [
        "/etc/passwd",
        "../outside.txt",
        "nested/../../outside.txt",
    ],
)
def test_validate_import_source_rejects_absolute_and_parent_traversal(tmp_path, monkeypatch, candidate) -> None:
    root = tmp_path / "imports"
    root.mkdir()
    monkeypatch.setattr(security, "IMPORT_ROOT", root)

    with pytest.raises(ValueError, match="inside the configured imports directory"):
        security.validate_import_source(candidate)


def test_validate_import_source_rejects_symlink(tmp_path, monkeypatch) -> None:
    root = tmp_path / "imports"
    root.mkdir()
    target = root / "real.txt"
    target.write_text("fixture", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    monkeypatch.setattr(security, "IMPORT_ROOT", root)

    with pytest.raises(ValueError, match="symlink ingest sources"):
        security.validate_import_source("link.txt")
