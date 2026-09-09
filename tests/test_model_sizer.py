from pathlib import Path

from pipeline.model_sizer import HardwareProfile, estimate_total_tokens, recommend_training_profile


def test_cpu_profile_is_small_and_bounded():
    hw = HardwareProfile("test", 4, 2.0, 0, 0.0, None, False)
    profile = recommend_training_profile(hw, total_tokens=1_000_000, configured_steps=100_000)
    assert profile.model_preset == "85M"
    assert profile.seq_len == 256
    assert profile.batch_size == 1
    assert profile.grad_accum_steps >= 16
    assert profile.recommended_steps is not None
    assert profile.recommended_steps < 100_000


def test_four_to_six_gb_profile_does_not_jump_model_size():
    hw = HardwareProfile("test", 8, 8.0, 1, 5.0, "test-gpu", True)
    profile = recommend_training_profile(hw)
    assert profile.model_preset == "85M"
    assert profile.seq_len == 512


def test_large_gpu_can_select_360m_preset():
    hw = HardwareProfile("test", 16, 32.0, 1, 24.0, "test-gpu", True)
    profile = recommend_training_profile(hw)
    assert profile.model_preset == "360M"
    assert profile.seq_len == 1024


def test_token_estimator_uses_manifest_dtype(tmp_path: Path):
    (tmp_path / "shard_00000_train.bin").write_bytes(b"\0" * 8)
    (tmp_path / "shard_00000_val.bin").write_bytes(b"\0" * 4)
    (tmp_path / "shards.manifest.json").write_text(
        '{"dtype":"uint16","files":[{"name":"shard_00000_train.bin","size":8},{"name":"shard_00000_val.bin","size":4}]}',
        encoding="utf-8",
    )
    assert estimate_total_tokens(tmp_path) == 6


def test_target_duration_requires_observed_throughput():
    hw = HardwareProfile("test", 8, 16.0, 1, 12.0, "test-gpu", True)
    profile = recommend_training_profile(hw, total_tokens=10_000_000, target_training_hours=1)
    assert profile.estimated_hours is None
