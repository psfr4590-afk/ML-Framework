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
    assert "smoke" in output
    assert "Bounded local smoke corpus" in output


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


def test_invalid_stages_do_not_construct_pipeline(monkeypatch, capsys):
    class ExplodingPipeline:
        def __init__(self, *args, **kwargs):
            raise AssertionError("invalid --stages must be rejected before Pipeline startup")

    import pipeline.orchestrator
    monkeypatch.setattr(pipeline.orchestrator, "Pipeline", ExplodingPipeline)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--stages", "crawl,not-a-stage"])

    assert run_pipeline.main() == 1
    output = capsys.readouterr().out
    assert "Unknown stages" in output
    assert "not-a-stage" in output
