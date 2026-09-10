from __future__ import annotations

import bootstrap


def test_python_requirement_message_is_current() -> None:
    message = bootstrap._python_requirement_message()
    assert "Python 3.11-3.13 required" in message
    assert "lxml 5.x" not in message


def test_python_requirement_message_does_not_claim_old_lxml_reason() -> None:
    message = bootstrap._python_requirement_message()
    assert "Python 3.14+ is not supported" in message
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
    assert summary["cuda_install_requested"] is True
    assert summary["hardware_warning"] is not None


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
