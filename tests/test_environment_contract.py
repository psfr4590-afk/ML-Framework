from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_reconciler_exists_and_is_referenced():
    script = ROOT / "scripts" / "reconcile_environment.py"
    assert script.is_file()
    source = (ROOT / "bootstrap.py").read_text(encoding="utf-8")
    assert "reconcile_environment.py" in source
    assert "--ensure-llamacpp" in source


def test_termux_safe_machine_tests_do_not_import_tkinter_at_collection_time():
    source = (ROOT / "tests/model_lab/test_machine_environment.py").read_text(encoding="utf-8")
    assert "import tkinter as tk" not in source
    assert 'pytest.importorskip("tkinter")' in source


def test_runtime_requirements_include_command_center_security_dependencies():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for package in ["fastapi", "uvicorn", "cryptography", "httpx", "pydantic"]:
        assert package in requirements


def test_semantic_acceleration_is_optional_for_termux():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    optional = (ROOT / "requirements-optional.txt").read_text(encoding="utf-8")
    assert "sentence-transformers" not in requirements
    assert "faiss-cpu" not in requirements
    assert "sentence-transformers" in optional
    assert "faiss-cpu" in optional


def test_native_bootstrap_has_android_profile():
    source = (ROOT / "scripts/bootstrap_llama_cpp.sh").read_text(encoding="utf-8")
    assert "TERMUX_VERSION" in source
    assert "GGML_NATIVE=OFF" in source
    assert "GGML_OPENMP=OFF" in source
    assert "llama-quantize" in source
    assert "llama-cli" not in source
    assert 'BUILD_DIR="build-model-lab"' in source
    assert "b10516" in source
    assert "b95502b" in source


def test_release_gate_cannot_skip_tests():
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert "--skip-tests" in source
    assert "not allowed for a production verification" in source
