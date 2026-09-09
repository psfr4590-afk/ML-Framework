import logging
import sys
from pathlib import Path

import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_list_groups_does_not_construct_pipeline(monkeypatch, capsys):
    class ExplodingPipeline:
        def __init__(self, *args, **kwargs):
            raise AssertionError("--list-groups must not construct Pipeline")

    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--list-groups"])
    monkeypatch.setitem(run_pipeline.__dict__, "_Pipeline_guard", ExplodingPipeline)

    import pipeline.orchestrator
    monkeypatch.setattr(pipeline.orchestrator, "Pipeline", ExplodingPipeline)

    assert run_pipeline.main() == 0
    output = capsys.readouterr().out
    assert "Configured dataset groups:" in output
    assert "swe_cs_systems" in output


def test_pipeline_log_level_is_reapplied_after_pipeline_initialization(monkeypatch):
    class FakePipeline:
        def __init__(self, *args, **kwargs):
            logging.getLogger().setLevel(logging.INFO)

        def run(self, *args, **kwargs):
            return None

    import pipeline.orchestrator
    monkeypatch.setattr(pipeline.orchestrator, "Pipeline", FakePipeline)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--log-level", "DEBUG"])

    run_pipeline.main()
    assert logging.getLogger().level == logging.DEBUG
