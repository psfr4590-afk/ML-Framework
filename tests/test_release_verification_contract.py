from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.patch_llama_cpp_tokenizer import patch_tokenizer_registry
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
    assert "--single-turn" in argv
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
    pipeline_sha = "a" * 64
    _write_local_smoke_input(scratch, pipeline_config_sha256=pipeline_sha)
    corpus = scratch / "04_weighted.jsonl"
    manifest = json.loads((scratch / "04_weighted.jsonl.manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(RELEASE_SMOKE_SOURCES) == 8
    assert len(rows) == 256
    assert {row["source"] for row in rows} == {source for source, _ in RELEASE_SMOKE_SOURCES}
    assert len({row["text"] for row in rows}) == 256
    assert len({row["meta"]["source_family"] for row in rows}) == 8
    assert sum("term" in row["text"] for row in rows) == 256
    assert manifest["provenance"]["pipeline_config_sha256"] == pipeline_sha
    assert manifest["provenance"]["stage"] == "weight"


def test_llama_cpp_tokenizer_overlay_registers_bytelevel_structurally(tmp_path: Path):
    llama_cpp = tmp_path / "llama.cpp"
    conversion = llama_cpp / "conversion"
    conversion.mkdir(parents=True)
    base = conversion / "base.py"
    base.write_text(
        "# Marker: Start get_vocab_base_pre\n"
        "    def get_vocab_base_pre(self, tokenizer):\n"
        "        res = None\n"
        "        if chkhsh == \"known\":\n"
        "            res = \"gpt-2\"\n",
        encoding="utf-8",
    )

    assert patch_tokenizer_registry(llama_cpp) is True
    patched = base.read_text(encoding="utf-8")
    assert 'pre_tokenizer.__class__.__name__ == "ByteLevel"' in patched
    assert 'res = "gpt-2"' in patched
    assert patch_tokenizer_registry(llama_cpp) is False
    assert base.read_text(encoding="utf-8") == patched


def test_llama_cpp_tokenizer_overlay_fails_closed_on_unknown_layout(tmp_path: Path):
    llama_cpp = tmp_path / "llama.cpp"
    conversion = llama_cpp / "conversion"
    conversion.mkdir(parents=True)
    (conversion / "base.py").write_text("def unrelated():\n    return None\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="generated get_vocab_base_pre marker is missing"):
        patch_tokenizer_registry(llama_cpp)


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
