from __future__ import annotations

from pathlib import Path

import torch

from pipeline.orchestrator import Pipeline
from pipeline.trainer.model import LlamaModel, ModelConfig
from pipeline.integrity import write_manifest
from scripts.export_gguf import _map_state
from command_center.store import DatasetStore


def test_pipeline_default_config_is_project_rooted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline()
    assert pipeline._project_root == Path(__file__).resolve().parents[1]
    assert pipeline._cfg_path == pipeline._project_root / "config" / "pipeline_config.yaml"


def test_model_param_count_respects_weight_tying():
