from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_gguf import verify_gguf
from scripts.verify_release import RELEASE_SMOKE_SOURCES, _write_local_smoke_input


class _Proc:
    returncode = 0
    stdout = "generated"
    stderr = ""


def test_verify_gguf_runs_one_token_generation(monkeypatch, tmp_path: Path):
    model = tmp_path / "model.gguf"
    cli = tmp_path / "llama-cli"
    model.write_bytes(b"gguf")
    cli.write_bytes(b"executable")
    seen: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return _Proc()

    monkeypatch.setattr("scripts.verify_gguf.subprocess.run", fake_run)
    result = verify_gguf(model, cli)

    command = result["generated_output"]
    assert command == "generated"
    argv = seen["cmd"]
    assert isinstance(argv, list)
    assert "-n" in argv and argv[argv.index("-n") + 1] == "1"
    assert "--no-display-prompt" in argv
    assert "--simple-io" in argv
    assert seen["kwargs"] == {"text": True, "capture_output": True, "check": False, "timeout": 120}


def test_verify_gguf_rejects_empty_generation(monkeypatch, tmp_path: Path):
    model = tmp_path / "model.gguf"
    cli = tmp_path / "llama-cli"
    model.write_bytes(b"gguf")
    cli.write_bytes(b"executable")

    class EmptyProc:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("scripts.verify_gguf.subprocess.run", lambda *args, **kwargs: EmptyProc())
    with pytest.raises(RuntimeError, match="generated no visible token output"):
        verify_gguf(model, cli)


def test_release_smoke_fixture_has_multiple_source_families_and_lexical_diversity(tmp_path: Path):
    scratch = tmp_path / "scratch"
    _write_local_smoke_input(scratch)
    corpus = scratch / "04_weighted.jsonl"
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(RELEASE_SMOKE_SOURCES) == 8
    assert len(rows) == 256
    assert {row["source"] for row in rows} == {source for source, _ in RELEASE_SMOKE_SOURCES}
    assert len({row["text"] for row in rows}) == 256
    assert len({row["meta"]["source_family"] for row in rows}) == 8
    assert sum("term" in row["text"] for row in rows) == 256


def test_release_gate_requires_native_flag_for_artifact_verification():
    source = Path("scripts/verify_release.py").read_text(encoding="utf-8")
    assert "STATIC VERIFICATION PASSED" in source
    assert "A production release requires --bootstrap-native" in source
    assert "scripts/verify_gguf.py" in source
    assert "inference_validation" in source


def test_release_verifier_runs_directly_from_repo_root():
    result = subprocess.run(
        [sys.executable, "scripts/verify_release.py", "--skip-tests"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--skip-tests is not allowed" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
