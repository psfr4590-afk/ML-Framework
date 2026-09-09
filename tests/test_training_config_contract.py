from pathlib import Path

import yaml

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
