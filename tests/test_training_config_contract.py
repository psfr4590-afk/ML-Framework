import json
from pathlib import Path

import torch
import yaml

from pipeline.trainer.train import latest_checkpoint, load_checkpoint

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))


def test_checkpoint_retention_is_configurable_and_generation_knob_is_not_dead_config():
    trainer = (ROOT / "pipeline" / "trainer" / "train.py").read_text(encoding="utf-8")
    assert 't.get("keep_checkpoints", 3)' in trainer
    assert 'keep=keep_checkpoints' in trainer
    assert "generate_every_steps" not in trainer

    for name in ("pipeline_config.yaml", "pipeline_config.smoke.yaml", "pipeline_config.full.yaml"):
        cfg = _load(name)
        train = cfg["train"]
        assert int(train["keep_checkpoints"]) >= 1
        assert "generate_every_steps" not in train


def test_latest_checkpoint_uses_highest_numeric_training_step(tmp_path):
    ckpt_dir = tmp_path / "checkpoints"
    ckpt_dir.mkdir()
    for name in ("ckpt_0000010.pt", "ckpt_0000009.pt", "ckpt_best_0000099.pt", "ckpt_final_0000100.pt"):
        path = ckpt_dir / name
        path.write_bytes(b"checkpoint")
        (ckpt_dir / f"{name}.manifest.json").write_text("{}", encoding="utf-8")

    assert latest_checkpoint(ckpt_dir).name == "ckpt_0000010.pt"


def test_load_checkpoint_rejects_stale_provenance(tmp_path):
    path = tmp_path / "ckpt_0000001.pt"
    model = torch.nn.Linear(2, 2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    # Keep the fixture above the loader's truncation guard so this test reaches
    # provenance validation rather than failing integrity validation first.
    torch.save(
        {
            "step": 1,
            "model": model.state_dict(),
            "padding": torch.zeros(1024, dtype=torch.float32),
        },
        path,
    )
    from pipeline.integrity import sha256_file

    manifest = {
        "schema": 2,
        "kind": "checkpoint",
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "step": 1,
        "val_loss": 1.0,
        "provenance": {"train_config_sha256": "old"},
    }
    (tmp_path / "ckpt_0000001.pt.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    try:
        load_checkpoint(
            path,
            model,
            optimizer=optimizer,
            expected_provenance={"train_config_sha256": "new"},
        )
    except RuntimeError as exc:
        assert "provenance mismatch" in str(exc).lower()
    else:
        raise AssertionError("stale checkpoint provenance was accepted")
