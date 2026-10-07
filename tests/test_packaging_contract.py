from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_dependency_authority_is_pyproject():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert [line for line in requirements if line.strip() and not line.lstrip().startswith("#")] == ["-e ."]

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = {item.split("[", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower() for item in project["project"]["dependencies"]}
    assert {"pyyaml", "requests", "numpy", "fastapi", "sentence-transformers", "faiss-cpu"} <= names


def test_legacy_ui_is_not_distributable_package():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    includes = project["tool"]["setuptools"]["packages"]["find"]["include"]
    assert all(not item.startswith("ui") for item in includes)
    assert (ROOT / "ui" / "README.md").is_file()
