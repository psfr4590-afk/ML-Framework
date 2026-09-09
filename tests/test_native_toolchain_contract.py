from pathlib import Path
from types import SimpleNamespace

import pipeline.doctor as doctor

ROOT = Path(__file__).resolve().parents[1]


def test_native_bootstrap_scripts_share_the_same_pin_and_required_tools():
    shell = (ROOT / "scripts/bootstrap_llama_cpp.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "scripts/bootstrap_llama_cpp.ps1").read_text(encoding="utf-8-sig")

    # The two bootstrap scripts use native variable syntax for their platform.
    assert 'TAG="b10516"' in shell
    assert 'COMMIT="b95502b"' in shell
    assert '$Tag = "b10516"' in powershell
    assert '$Commit = "b95502b"' in powershell

    for content in (shell, powershell):
        assert "convert_hf_to_gguf.py" in content
        assert "llama-quantize" in content
        assert "--target" in content


def test_native_doctor_rejects_wrong_revision(monkeypatch, tmp_path):
    target = tmp_path / "third_party" / "llama.cpp"
    target.mkdir(parents=True)
    (target / ".git").mkdir()
    (target / "convert_hf_to_gguf.py").write_text("# fixture\n", encoding="utf-8")
    (target / "llama-quantize").write_text("fixture", encoding="utf-8")

    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="deadbeef1234\n"),
    )

    ok, detail = doctor._llamacpp_state(tmp_path)
    assert not ok
    assert "revision mismatch" in detail
    assert "b95502b" in detail


def test_native_doctor_accepts_pinned_revision(monkeypatch, tmp_path):
    target = tmp_path / "third_party" / "llama.cpp"
    target.mkdir(parents=True)
    (target / ".git").mkdir()
    (target / "convert_hf_to_gguf.py").write_text("# fixture\n", encoding="utf-8")
    (target / "llama-quantize").write_text("fixture", encoding="utf-8")

    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="b95502b9999\n"),
    )

    ok, detail = doctor._llamacpp_state(tmp_path)
    assert ok
    assert "b10516" in detail
    assert "b95502b" in detail
