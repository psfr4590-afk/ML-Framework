from pathlib import Path

import yaml

from pipeline.config_validation import validate_config

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_main_config_is_validator_clean():
    validate_config(load_yaml(ROOT / "config" / "pipeline_config.yaml"))


def test_smoke_config_is_validator_clean():
    validate_config(load_yaml(ROOT / "config" / "pipeline_config.smoke.yaml"))


def test_pipeline_level_model_preset_is_rejected():
    cfg = load_yaml(ROOT / "config" / "pipeline_config.yaml")
    cfg["pipeline"]["model_preset"] = "85M"
    try:
        validate_config(cfg)
    except ValueError as exc:
        assert "pipeline.model_preset is obsolete" in str(exc)
    else:
        raise AssertionError("obsolete pipeline.model_preset must be rejected")
