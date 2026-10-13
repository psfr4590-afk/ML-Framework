from __future__ import annotations

import bootstrap


def test_python_requirement_message_is_current() -> None:
    message = bootstrap._python_requirement_message()
    assert "Python 3.11-3.14 required" in message
    assert "lxml 5.x" not in message


def test_python_requirement_message_does_not_claim_old_lxml_reason() -> None:
    message = bootstrap._python_requirement_message()
    assert "Python 3.15+ is not supported" in message
    assert "dependency compatibility" in message


def test_hardware_profile_defaults_to_unknown() -> None:
    profile = bootstrap.HardwareProfile()
    assert profile.ram_gib is None
    assert profile.gpu_name is None
    assert profile.gpu_vram_gib is None
    assert profile.nvidia_smi_available is False


def test_torch_channel_summary_cpu() -> None:
    profile = bootstrap.HardwareProfile(ram_gib=8.0, gpu_name="NVIDIA GeForce GTX 1650", gpu_vram_gib=4.0)
    summary = bootstrap.torch_channel_summary("cpu", profile)
    assert summary["selected_channel"] == "cpu"
    assert summary["gpu_detected"] is True
    assert summary["cuda_install_requested"] is False


def test_torch_channel_summary_default_is_explicit() -> None:
    profile = bootstrap.HardwareProfile(ram_gib=8.0, gpu_name="NVIDIA GeForce GTX 1650", gpu_vram_gib=4.0)
    summary = bootstrap.torch_channel_summary("default", profile)
    assert summary["selected_channel"] == "default"
    assert summary["gpu_detected"] is True
    assert summary["cuda_install_requested"] is False
    assert summary["hardware_warning"] is not None


def test_torch_channel_summary_cuda() -> None:
    profile = bootstrap.HardwareProfile(ram_gib=8.0, gpu_name="NVIDIA GeForce GTX 1650", gpu_vram_gib=4.0)
    summary = bootstrap.torch_channel_summary("cuda", profile)
    assert summary["selected_channel"] == "cuda"
    assert summary["gpu_detected"] is True
    assert summary["cuda_install_requested"] is True
    assert summary["hardware_warning"] is None


def test_hardware_profile_json_is_stable() -> None:
    profile = bootstrap.HardwareProfile(
        ram_gib=8.0,
        cpu_name="AMD Ryzen 5 4600H with Radeon Graphics",
        cpu_cores=6,
        cpu_threads=12,
        gpu_name="NVIDIA GeForce GTX 1650",
        gpu_vram_gib=4.0,
        nvidia_smi_available=True,
    )
    assert profile.as_dict() == {
        "ram_gib": 8.0,
        "cpu_name": "AMD Ryzen 5 4600H with Radeon Graphics",
        "cpu_cores": 6,
        "cpu_threads": 12,
        "gpu_name": "NVIDIA GeForce GTX 1650",
        "gpu_vram_gib": 4.0,
        "nvidia_smi_available": True,
    }


def test_bootstrap_required_runtime_dependencies_include_semantic_dedup() -> None:
    assert "sentence_transformers" in bootstrap.REQUIRED
    assert "faiss" in bootstrap.REQUIRED


def test_torch_variant_matches_cuda_and_cpu(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.11.0+cu128")
    assert bootstrap._torch_variant_matches("cuda")
    assert not bootstrap._torch_variant_matches("cpu")

    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.14.1+cpu")
    assert not bootstrap._torch_variant_matches("cuda")
    assert bootstrap._torch_variant_matches("cpu")


def test_torch_variant_matches_missing(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: None)
    assert not bootstrap._torch_variant_matches("cuda")


def test_validate_cuda_torch_rejects_cpu_variant(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.14.1+cpu")
    assert bootstrap._validate_requested_torch_channel("cuda") == 2


def test_validate_cpu_torch_rejects_cuda_variant(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.11.0+cu128")
    assert bootstrap._validate_requested_torch_channel("cpu") == 2


def test_doctor_accepts_working_cpu_torch_when_nvidia_gpu_is_present(monkeypatch, capsys) -> None:
    profile = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650", gpu_vram_gib=4.0)
    monkeypatch.setattr(bootstrap, "detect_hardware", lambda: profile)
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {
            "installed": True,
            "importable": True,
            "version": "2.14.1+cpu",
            "cuda_available": False,
            "cuda_version": None,
            "device_count": 0,
        },
    )
    monkeypatch.setattr(bootstrap, "_importable", lambda name: True)
    monkeypatch.setattr(bootstrap.RECONCILER.__class__, "is_file", lambda self: True)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda exe: "present")

    assert bootstrap.doctor() == 0
    output = capsys.readouterr().out
    assert "CUDA unavailable; CPU execution remains available." in output
    assert "Bootstrap doctor: PASS" in output



def test_doctor_reports_cuda_probe_error_and_keeps_cpu_fallback(
    monkeypatch, capsys
) -> None:
    profile = bootstrap.HardwareProfile(
        gpu_name="NVIDIA GeForce GTX 1650",
        gpu_vram_gib=4.0,
    )
    monkeypatch.setattr(bootstrap, "detect_hardware", lambda: profile)
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {
            "installed": True,
            "importable": True,
            "version": "2.11.0+cu128",
            "cuda_available": False,
            "cuda_version": "12.8",
            "device_count": 0,
            "cuda_error": "OSError: CUDA runtime probe blocked",
        },
    )
    monkeypatch.setattr(bootstrap, "_importable", lambda name: True)
    monkeypatch.setattr(bootstrap.RECONCILER.__class__, "is_file", lambda self: True)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda exe: "present")

    assert bootstrap.doctor() == 0
    output = capsys.readouterr().out
    assert "CUDA unavailable; CPU execution remains available." in output
    assert "CUDA probe error: OSError: CUDA runtime probe blocked" in output
    assert "Bootstrap doctor: PASS" in output

def test_torch_runtime_status_reports_installed_but_blocked_import(monkeypatch) -> None:
    def blocked_import(name):
        if name == "torch":
            raise OSError("application control blocked torch DLL")
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(bootstrap.importlib, "import_module", blocked_import)
    monkeypatch.setattr(bootstrap.importlib.metadata, "version", lambda name: "2.11.0+cu128")

    status = bootstrap.torch_runtime_status()
    assert status["installed"] is True
    assert status["importable"] is False
    assert status["version"] == "2.11.0+cu128"
    assert "application control blocked torch DLL" in status["error"]


def test_torch_runtime_status_reports_cuda_probe_failure(monkeypatch) -> None:
    class FakeCuda:
        @staticmethod
        def is_available():
            raise OSError("CUDA runtime probe blocked")

    class FakeTorch:
        __version__ = "2.11.0+cu128"
        cuda = FakeCuda()
        version = type("Version", (), {"cuda": "12.8"})()

    monkeypatch.setattr(bootstrap.importlib, "import_module", lambda name: FakeTorch())

    status = bootstrap.torch_runtime_status()
    assert status["installed"] is True
    assert status["importable"] is True
    assert status["cuda_available"] is False
    assert "CUDA runtime probe blocked" in status["cuda_error"]


def test_torch_runtime_status_reports_device_count_failure(monkeypatch) -> None:
    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def device_count():
            raise RuntimeError("device enumeration failed")

    class FakeTorch:
        __version__ = "2.11.0+cu128"
        cuda = FakeCuda()
        version = type("Version", (), {"cuda": "12.8"})()

    monkeypatch.setattr(bootstrap.importlib, "import_module", lambda name: FakeTorch())

    status = bootstrap.torch_runtime_status()
    assert status["importable"] is True
    assert status["cuda_available"] is False
    assert status["device_count"] == 0
    assert "device enumeration failed" in status["cuda_error"]


def test_cuda_channel_validation_rejects_cuda_probe_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.11.0+cu128")
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {
            "installed": True,
            "importable": True,
            "cuda_available": False,
            "cuda_error": "OSError: CUDA runtime probe blocked",
        },
    )

    assert bootstrap._validate_requested_torch_channel("cuda") == 2
    assert "CUDA runtime probe blocked" in capsys.readouterr().err


def test_cpu_channel_validation_rejects_unimportable_torch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(bootstrap, "_installed_torch_version", lambda: "2.14.1+cpu")
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {
            "installed": True,
            "importable": False,
            "cuda_available": False,
            "error": "OSError: blocked DLL",
        },
    )
    assert bootstrap._validate_requested_torch_channel("cpu") == 2
    assert "blocked DLL" in capsys.readouterr().err
