from __future__ import annotations

from pipeline.model_sizer import HardwareProfile, recommend_training_profile
from pipeline.preflight import estimate_duration


def test_sub_4gb_profile_matches_low_vram_contract():
    hw = HardwareProfile("test", 4, 2.0, 1, 3.99, "test-gpu", True)
    profile = recommend_training_profile(hw)
    assert profile.model_preset == "85M"
    assert profile.seq_len == 128
    assert profile.batch_size == 1
    assert profile.grad_accum_steps == 32
    assert "VRAM < 4 GB" in profile.decision_reasons


def test_hardware_snapshot_contains_phase5_fields():
    hw = HardwareProfile(
        "test", 4, 2.0, 1, 3.99, "test-gpu", True,
        total_ram_gb=8.0, cpu_threads=8, cpu_name="test-cpu",
        cuda_version="12.8", driver_version="555.1", pytorch_version="2.14.0",
        os_name="Windows", disk_free_gb=50.0, disk_total_gb=100.0,
    )
    data = hw.to_dict()
    assert data["total_ram_gb"] == 8.0
    assert data["cpu_threads"] == 8
    assert data["driver_version"] == "555.1"
    assert data["pytorch_version"] == "2.14.0"
    assert data["disk_free_gb"] == 50.0


def test_duration_estimate_records_live_schedule():
    estimate = estimate_duration(
        total_steps=100, batch_size=1, grad_accum_steps=32, seq_len=128,
        tokens_per_sec=1280.0, eval_every_steps=20, eval_batches=2,
        checkpoint_every_steps=50,
    )
    assert estimate["estimated_duration_seconds"] is not None
    assert len(estimate["estimated_checkpoint_times"]) == 2
    assert len(estimate["estimated_eval_times"]) == 5
    assert estimate["estimated_completion"] is not None


def test_duration_estimate_requires_benchmark_throughput():
    estimate = estimate_duration(
        total_steps=100, batch_size=1, grad_accum_steps=32, seq_len=128,
        tokens_per_sec=None, eval_every_steps=20, eval_batches=2,
        checkpoint_every_steps=50,
    )
    assert estimate["estimated_duration_seconds"] is None
