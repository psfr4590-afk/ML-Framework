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

    assert result["cuda_available"] is False
    assert result["device_count"] == 0
    assert any("device_count" in error and "driver enumeration failed" in error for error in result["probe_errors"])


def test_requirement_validation_checks_version_constraints():
    assert bootstrap._requirement_satisfied("numpy>=1.26,<3", "2.0.0")
    assert not bootstrap._requirement_satisfied("numpy>=1.26,<3", "3.0.0")
    assert not bootstrap._requirement_satisfied("fastapi>=0.141.1,<1", "0.100.0")


def test_source_import_audit_flags_unmapped_third_party_import(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    (tmp_path / "sample.py").write_text(
        "import json\nimport torch\nimport unlisted_external_package\n",
        encoding="utf-8",
    )

    issues = bootstrap._source_import_dependency_issues({"torch"})

    assert "unmapped third-party source import: unlisted_external_package" in issues
    assert not any("json" in issue for issue in issues)
    assert not any("torch" in issue for issue in issues)


def test_source_import_audit_accepts_declared_distribution(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    (tmp_path / "sample.py").write_text("import json\nimport numpy\n", encoding="utf-8")

    assert bootstrap._source_import_dependency_issues({"numpy"}) == []


def test_runtime_status_preserves_cuda_probe_error_field(monkeypatch):
    class FakeCuda:
        @staticmethod
        def is_available():
            raise OSError("CUDA runtime probe blocked")

    class FakeTorch:
        __version__ = "test"
        cuda = FakeCuda()
        version = type("Version", (), {"cuda": "12.8", "hip": None})()
        xpu = type("Xpu", (), {"is_available": staticmethod(lambda: False)})()
        backends = type("Backends", (), {"mps": type("Mps", (), {"is_available": staticmethod(lambda: False)})()})()

    monkeypatch.setattr(bootstrap.importlib.metadata, "version", lambda name: "2.11.0")
    monkeypatch.setattr(bootstrap.importlib, "import_module", lambda name: FakeTorch())
    result = bootstrap.torch_runtime_status()

    assert result["cuda_available"] is False
    assert result["device_count"] == 0
    assert "CUDA runtime probe blocked" in result["cuda_error"]


def test_source_import_audit_ignores_isolated_ci_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    (tmp_path / "sample.py").write_text("import json\nimport numpy\n", encoding="utf-8")
    generated_package = tmp_path / ".ci-venv" / "lib" / "site-packages" / "unrelated_vendor_pkg"
    generated_package.mkdir(parents=True)
    (generated_package / "__init__.py").write_text(
        "import dependency_that_is_not_part_of_this_project\n", encoding="utf-8"
    )

    assert bootstrap._source_import_dependency_issues({"numpy"}) == []


def test_security_tool_is_declared_as_optional_dependency():
    optional = {name.lower().replace("_", "-") for name in bootstrap._declared_optional_runtime_distributions()}

    assert "pip-audit" in optional
    assert bootstrap.DISTRIBUTION_IMPORTS["pip-audit"] == "pip_audit"


def test_runtime_recommendation_covers_unavailable_and_cpu_only_states():
    gpu = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650")
    no_gpu = bootstrap.HardwareProfile()

    assert bootstrap.recommended_torch_channel(
        gpu, {"importable": False, "cuda_available": False}
    ).startswith("manual review required")
    assert bootstrap.recommended_torch_channel(
        no_gpu, {"importable": True, "cuda_available": False}
    ) == "cpu"


def test_torch_runtime_status_reports_installed_but_blocked_import(monkeypatch):
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


def test_torch_runtime_status_preserves_cuda_probe_failure(monkeypatch):
    class FakeCuda:
        @staticmethod
        def is_available():
            raise OSError("CUDA runtime probe blocked")

    class FakeTorch:
        __version__ = "2.11.0+cu128"
        cuda = FakeCuda()
        version = type("Version", (), {"cuda": "12.8", "hip": None})()

    monkeypatch.setattr(bootstrap.importlib.metadata, "version", lambda name: "2.11.0+cu128")
    monkeypatch.setattr(bootstrap.importlib, "import_module", lambda name: FakeTorch())

    status = bootstrap.torch_runtime_status()

    assert status["installed"] is True
    assert status["importable"] is True
    assert status["cuda_available"] is False
    assert "CUDA runtime probe blocked" in status["cuda_error"]


def test_cuda_channel_validation_preserves_probe_failure_detail(monkeypatch, capsys):
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


def test_cpu_channel_validation_rejects_unimportable_torch(monkeypatch, capsys):
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


def test_doctor_reports_cuda_probe_error_and_keeps_cpu_fallback(monkeypatch, capsys):
    profile = bootstrap.HardwareProfile(gpu_name="NVIDIA GeForce GTX 1650", gpu_vram_gib=4.0)
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
            "hip_available": False,
            "xpu_available": False,
            "mps_available": False,
            "device_count": 0,
            "cuda_error": "OSError: CUDA runtime probe blocked",
            "probe_errors": ["cuda: OSError: CUDA runtime probe blocked"],
        },
    )
    monkeypatch.setattr(bootstrap, "_importable", lambda name: True)
    monkeypatch.setattr(bootstrap.RECONCILER.__class__, "is_file", lambda self: True)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda exe: "present")

    assert bootstrap.doctor() == 0
    output = capsys.readouterr().out
    assert "Accelerator probe error: cuda: OSError: CUDA runtime probe blocked" in output
    assert "Verified runtime recommendation: cpu (CUDA unavailable)" in output
    assert "Bootstrap doctor: PASS" in output
