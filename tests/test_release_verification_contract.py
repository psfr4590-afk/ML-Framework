from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_gguf import verify_gguf


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


def test_release_gate_requires_native_flag_for_artifact_verification():
    source = Path("scripts/verify_release.py").read_text(encoding="utf-8")
    assert "STATIC VERIFICATION PASSED" in source
    assert "A production release requires --bootstrap-native" in source
    assert "scripts/verify_gguf.py" in source
    assert "inference_validation" in source
