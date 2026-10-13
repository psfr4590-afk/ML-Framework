from __future__ import annotations

import bootstrap


def test_hardware_profile_recognizes_nvidia_from_adapter_name():
    profile = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650")

    assert profile.nvidia_gpu_detected
    assert profile.gpu_detected


def test_hardware_profile_recognizes_amd_and_intel_adapters():
    amd = bootstrap.HardwareProfile(
        gpu_name="AMD Radeon Graphics",
        gpu_vendor=bootstrap._gpu_vendor("AMD Radeon Graphics"),
    )
    intel = bootstrap.HardwareProfile(
        gpu_name="Intel Arc Graphics",
        gpu_vendor=bootstrap._gpu_vendor("Intel Arc Graphics"),
    )

    assert amd.gpu_vendor == "amd"
    assert intel.gpu_vendor == "intel"
    assert not amd.nvidia_gpu_detected
    assert not intel.nvidia_gpu_detected


def test_runtime_recommendation_uses_verified_cuda_not_gpu_presence_alone():
    profile = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650")
    runtime = {"installed": True, "importable": True, "cuda_available": False}

    # Doctor may recommend CPU as a diagnosed fallback; auto-install still refuses silent fallback.
    assert bootstrap.recommended_torch_channel(profile, runtime) == "cpu (CUDA unavailable)"


def test_runtime_recommendation_allows_verified_cuda():
    profile = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650")
    runtime = {"installed": True, "importable": True, "cuda_available": True}

    assert bootstrap.recommended_torch_channel(profile, runtime) == "cuda (usable)"


def test_runtime_recommendation_keeps_verified_intel_xpu():
    profile = bootstrap.HardwareProfile(
        gpu_name="Intel Arc Graphics",
        gpu_vendor="intel",
    )
    runtime = {"installed": True, "importable": True, "xpu_available": True}

    assert bootstrap.recommended_torch_channel(profile, runtime) == "xpu (usable)"


def test_runtime_recommendation_does_not_silently_fall_back_for_amd_gpu():
    profile = bootstrap.HardwareProfile(
        gpu_name="AMD Radeon Graphics",
        gpu_vendor="amd",
    )
    runtime = {"installed": False, "importable": False}

    assert bootstrap.recommended_torch_channel(profile, runtime).startswith(
        "manual review required"
    )


def test_runtime_recommendation_uses_cpu_when_no_gpu_is_detected():
    profile = bootstrap.HardwareProfile()
    runtime = {"installed": False, "importable": False}

    assert bootstrap.recommended_torch_channel(profile, runtime) == "cpu"


def test_runtime_dependency_inventory_comes_from_pyproject_metadata():
    names = {name.lower() for name in bootstrap._declared_runtime_distributions()}

    assert "pyyaml" in names
    assert "requests" in names
    assert "fastapi" in names
    assert "faiss-cpu" in names
    assert "torch" not in names

def test_runtime_recommendation_keeps_verified_amd_rocm():
    profile = bootstrap.HardwareProfile(
        gpu_name="AMD Radeon Graphics",
        gpu_vendor="amd",
    )
    runtime = {"installed": True, "importable": True, "cuda_available": True, "hip_available": True}

    assert bootstrap.recommended_torch_channel(profile, runtime) == "rocm (usable)"

def test_every_declared_runtime_distribution_has_an_import_probe():
    declared = {
        name.lower().replace("_", "-")
        for name in bootstrap._declared_runtime_distributions()
    }

    assert declared - set(bootstrap.DISTRIBUTION_IMPORTS) == set()
    assert "torch" not in declared

def test_auto_install_selects_rocm_for_amd_gpu_on_linux(monkeypatch):
    profile = bootstrap.HardwareProfile(
        gpu_name="AMD Radeon Graphics",
        gpu_vendor="amd",
    )
    calls = []
    monkeypatch.setattr(bootstrap.sys, "platform", "linux")
    monkeypatch.setattr(bootstrap, "detect_hardware", lambda: profile)
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {"installed": False, "importable": False, "hip_available": False},
    )
    monkeypatch.setattr(bootstrap, "_remove_incompatible_torch", lambda channel: calls.append(("remove", channel)) or 0)
    monkeypatch.setattr(bootstrap, "_pip_install", lambda requirements, *extra: calls.append((str(requirements), *extra)) or 0)
    monkeypatch.setattr(bootstrap, "_validate_requested_torch_channel", lambda channel: calls.append(("validate", channel)) or 0)

    assert bootstrap.install("auto") == 0
    assert ("remove", "rocm") in calls
    assert (str(bootstrap.TORCH_REQUIREMENTS), "--index-url", bootstrap.ROCM_TORCH_INDEX) in calls
    assert ("validate", "rocm") in calls


def test_auto_install_selects_xpu_for_intel_gpu(monkeypatch):
    profile = bootstrap.HardwareProfile(
        gpu_name="Intel Arc Graphics",
        gpu_vendor="intel",
    )
    calls = []
    monkeypatch.setattr(bootstrap.sys, "platform", "linux")
    monkeypatch.setattr(bootstrap, "detect_hardware", lambda: profile)
    monkeypatch.setattr(
        bootstrap,
        "torch_runtime_status",
        lambda: {"installed": False, "importable": False, "xpu_available": False},
    )
    monkeypatch.setattr(bootstrap, "_remove_incompatible_torch", lambda channel: calls.append(("remove", channel)) or 0)
    monkeypatch.setattr(bootstrap, "_pip_install", lambda requirements, *extra: calls.append((str(requirements), *extra)) or 0)
    monkeypatch.setattr(bootstrap, "_validate_requested_torch_channel", lambda channel: calls.append(("validate", channel)) or 0)

    assert bootstrap.install("auto") == 0
    assert ("remove", "xpu") in calls
    assert (str(bootstrap.TORCH_REQUIREMENTS), "--index-url", bootstrap.XPU_TORCH_INDEX) in calls
    assert ("validate", "xpu") in calls

def test_explicit_gpu_runtime_is_rejected_without_matching_hardware(monkeypatch, capsys):
    monkeypatch.setattr(bootstrap, "detect_hardware", lambda: bootstrap.HardwareProfile())
    install_calls = []
    monkeypatch.setattr(bootstrap, "_pip_install", lambda *args: install_calls.append(args) or 0)

    assert bootstrap.install("cuda") == 2
    assert install_calls == []
    assert "no compatible GPU/platform was detected" in capsys.readouterr().err


def test_runtime_status_catches_cuda_device_count_errors(monkeypatch):
    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def device_count():
            raise RuntimeError("driver enumeration failed")

    class FakeTorch:
        __version__ = "test"
        cuda = FakeCuda()
        version = type("Version", (), {"cuda": "12.8", "hip": None})()
        xpu = type("Xpu", (), {"is_available": staticmethod(lambda: False)})()
        backends = type("Backends", (), {"mps": type("Mps", (), {"is_available": staticmethod(lambda: False)})()})()

    monkeypatch.setattr(bootstrap.importlib.metadata, "version", lambda name: "2.11.0")
    monkeypatch.setattr(bootstrap.importlib, "import_module", lambda name: FakeTorch())
    result = bootstrap.torch_runtime_status()

    assert result["cuda_available"] is True
    assert result["device_count"] == 0
    assert any("device_count" in error and "driver enumeration failed" in error for error in result["probe_errors"])


def test_requirement_validation_checks_version_constraints():
    assert bootstrap._requirement_satisfied("numpy>=1.26,<3", "2.0.0")
    assert not bootstrap._requirement_satisfied("numpy>=1.26,<3", "3.0.0")
    assert not bootstrap._requirement_satisfied("fastapi>=0.141.1,<1", "0.100.0")
