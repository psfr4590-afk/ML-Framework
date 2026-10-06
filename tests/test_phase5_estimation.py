from __future__ import annotations

import json

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


def test_preflight_runtime_failure_is_non_viable(monkeypatch, tmp_path):
    from pipeline import preflight

    def fail_model(_train_cfg):
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(preflight, "_make_model", fail_model)
    result = preflight.run_preflight({"model_preset": "85M", "seq_len": 128}, tmp_path)
    assert result.viable is False
    assert result.tokens_per_sec is None
    assert "out of memory" in result.failure.lower()


def test_preflight_report_persists_benchmark_and_estimate(tmp_path):
    from pipeline.preflight import PreflightResult, write_preflight_report

    result = PreflightResult(
        viable=True,
        tokens_per_sec=2048.0,
        steps_per_sec=16.0,
        peak_memory_gb=3.2,
        gpu_utilization_percent=87.0,
        benchmark_seconds=1.25,
        warmup_steps=1,
        benchmark_steps=3,
    )
    estimate = estimate_duration(
        total_steps=100,
        batch_size=1,
        grad_accum_steps=32,
        seq_len=128,
        tokens_per_sec=result.tokens_per_sec,
        eval_every_steps=20,
        eval_batches=2,
        checkpoint_every_steps=50,
    )
    path = tmp_path / "preflight_report.json"
    write_preflight_report(path, {
        "hardware": {"gpu_name": "test-gpu", "gpu_memory_gb": 3.99},
        "requested_configuration": {"model_preset": "117M", "seq_len": 512},
        "effective_configuration": {"model_preset": "85M", "seq_len": 128},
        "decision_reasons": ["VRAM < 4 GB"],
        "benchmark": result.to_dict(),
        "estimate": estimate,
    })
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["benchmark"]["tokens_per_sec"] == 2048.0
    assert data["benchmark"]["peak_memory_gb"] == 3.2
    assert data["estimate"]["estimated_duration_seconds"] is not None
    assert data["requested_configuration"]["model_preset"] == "117M"
    assert data["effective_configuration"]["model_preset"] == "85M"


def test_trainer_blocks_training_when_preflight_fails(monkeypatch, tmp_path):
    import pytest
    from pipeline.trainer import train as train_module
    from pipeline.model_sizer import HardwareProfile
    from pipeline.preflight import PreflightResult

    hardware = HardwareProfile("test", 4, 2.0, 1, 3.99, "test-gpu", True)

    monkeypatch.setattr(train_module, "profile_hardware", lambda: hardware)
    monkeypatch.setattr(
        train_module,
        "run_preflight",
        lambda *args, **kwargs: PreflightResult(
            viable=False,
            tokens_per_sec=None,
            steps_per_sec=None,
            peak_memory_gb=3.99,
            gpu_utilization_percent=None,
            benchmark_seconds=0.1,
            warmup_steps=1,
            benchmark_steps=3,
            failure="RuntimeError: out of memory",
        ),
    )

    def should_not_start(*args, **kwargs):
        raise AssertionError("model construction must not occur after a failed preflight")

    monkeypatch.setattr(train_module, "LlamaModel", should_not_start)
    cfg = {
        "pipeline": {"output_dir": str(tmp_path)},
        "train": {
            "allow_cpu_training": True,
            "model_preset": "85M",
            "seq_len": 128,
            "batch_size": 1,
            "grad_accum_steps": 1,
            "total_steps": 2,
        },
        "shard": {"sequence_length": 128},
        "preflight": {"enabled": True, "warmup_steps": 1, "benchmark_steps": 3},
    }

    with pytest.raises(RuntimeError, match="Preflight rejected training configuration"):
        train_module.Trainer(cfg).run()


def test_training_metadata_preserves_phase5_lineage(tmp_path):
    from pipeline.trainer.train import Trainer

    cfg = {
        "pipeline": {"output_dir": str(tmp_path)},
        "train": {},
    }
    trainer = Trainer(cfg)
    trainer._hardware_profile = {"gpu_name": "test-gpu", "gpu_memory_gb": 3.99}
    trainer._requested_configuration = {"model_preset": "117M", "seq_len": 512}
    trainer._initial_estimate_seconds = 123.5

    class FakeModel:
        def parameters(self):
            return []

    metadata = trainer._training_metadata(
        FakeModel(),
        {
            "model_preset": "85M",
            "seq_len": 128,
            "_hardware_profile": trainer._hardware_profile,
            "_preflight": {"viable": True, "tokens_per_sec": 2048.0},
        },
        seed=42,
        step=10,
        total_steps=100,
        batch_size=1,
        grad_accum=32,
        seq_len=128,
        tokens_processed=40960,
        start_time=__import__("time").time() - 10,
        evaluation_duration=1.0,
        checkpoint_duration=2.0,
    )

    assert metadata["hardware_profile"]["gpu_memory_gb"] == 3.99
    assert metadata["requested_configuration"]["model_preset"] == "117M"
    assert metadata["preflight"]["tokens_per_sec"] == 2048.0
    assert metadata["initial_estimate_seconds"] == 123.5
    assert metadata["estimated_vs_actual_seconds"]["estimated_seconds"] == 123.5
    assert metadata["estimated_vs_actual_seconds"]["actual_seconds"] >= 0


def test_checkpoint_manifest_preserves_phase5_metadata(tmp_path):
    import torch
    from pipeline.trainer.train import save_checkpoint

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(1))
            self.cfg = type("Cfg", (), {"to_dict": lambda self: {"test": True}})()

    class TinyScaler:
        def state_dict(self):
            return {"scale": 1.0}

    model = TinyModel()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    provenance = {"schema": 3, "run_id": "test-run", "source_manifest_sha256": "a" * 64}
    training_metadata = {
        "hardware_profile": {"gpu_name": "test-gpu", "gpu_memory_gb": 3.99},
        "requested_configuration": {"model_preset": "117M"},
        "effective_configuration": {"model_preset": "85M"},
        "preflight": {"viable": True, "tokens_per_sec": 2048.0},
        "initial_estimate_seconds": 123.5,
        "estimated_vs_actual_seconds": {"estimated_seconds": 123.5, "actual_seconds": 120.0},
    }

    path = save_checkpoint(
        model,
        optimizer,
        TinyScaler(),
        step=10,
        val_loss=1.5,
        cfg={"train": {"model_preset": "85M"}},
        out_dir=tmp_path,
        tag="final",
        provenance=provenance,
        training_metadata=training_metadata,
        final_step=10,
    )

    manifest = json.loads(path.with_name(path.name + ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["provenance"] == provenance

    payload = torch.load(path, map_location="cpu", weights_only=False)
    metadata = payload["training_metadata"]
    assert metadata["hardware_profile"]["gpu_memory_gb"] == 3.99
    assert metadata["requested_configuration"]["model_preset"] == "117M"
    assert metadata["effective_configuration"]["model_preset"] == "85M"
    assert metadata["preflight"]["tokens_per_sec"] == 2048.0
    assert metadata["estimated_vs_actual_seconds"]["actual_seconds"] == 120.0


def test_capability_discovery_records_verified_and_failed_probe(monkeypatch):
    import torch
    from pipeline import preflight
    from pipeline.model_sizer import HardwareProfile

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.ones(1))

        def forward(self, x, y):
            loss = (self.weight * (x.float().mean() - y.float().mean()) * 0 + self.weight.pow(2)).mean()
            return None, loss

    def make_model(cfg):
        if int(cfg["seq_len"]) == 512:
            raise RuntimeError("synthetic probe failure")
        return TinyModel()

    monkeypatch.setattr(preflight, "_make_model", make_model)
    hw = HardwareProfile("test", 4, 8.0, 0, 0.0, None, False)
    report = preflight.discover_capabilities(
        hw,
        candidates=(("85M", 256), ("117M", 512)),
        benchmark_steps=1,
        vocab_size=32,
    )
    assert report["tested_combinations"] == 2
    assert report["results"][0]["viable"] is True
    assert report["results"][1]["viable"] is False
    assert "synthetic probe failure" in report["results"][1]["failure"]
