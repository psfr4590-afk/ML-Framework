

def test_refresh_pipeline_state_rejects_existing_but_unverified_artifact(tmp_path, monkeypatch):
    import command_center.store as store_module

    monkeypatch.setattr(store_module, "DATASETS", tmp_path)
    store = store_module.DatasetStore()
    meta = store.create("state-test", group_config={"id": "test", "name": "test", "sources": {}})
    root = store.path(meta["id"])
    artifact = root / "scratch" / "02_cleaned.jsonl"
    artifact.write_text('{"text":"stale"}\n', encoding="utf-8")

    state = store.refresh_pipeline_state(meta["id"])
    assert state["stages"]["clean"] == "stale"
    assert state["status"] == "STALE"


def test_refresh_pipeline_state_accepts_verified_jsonl_artifact(tmp_path, monkeypatch):
    import command_center.store as store_module
    from pipeline.integrity import write_manifest

    monkeypatch.setattr(store_module, "DATASETS", tmp_path)
    store = store_module.DatasetStore()
    meta = store.create("state-test", group_config={"id": "test", "name": "test", "sources": {}})
    artifact = store.path(meta["id"]) / "scratch" / "02_cleaned.jsonl"
    artifact.write_text('{"text":"verified"}\n', encoding="utf-8")
    write_manifest(artifact, kind="clean", rows=1)

    state = store.refresh_pipeline_state(meta["id"])
    assert state["stages"]["clean"] == "complete"


def test_start_stage_rejects_second_start_during_thread_start(monkeypatch):
    import command_center.runner as runner

    class Dataset:
        def __getitem__(self, key):
            if key == "stages":
                return {"crawl": "pending"}
            raise KeyError(key)

    monkeypatch.setattr(runner.store, "get", lambda did: Dataset())
    monkeypatch.setattr(runner.threading, "Thread", lambda **kwargs: type("T", (), {"start": lambda self: None})())
    runner.RUNS.clear()

    assert runner.start_stage(1, "crawl")["started"] is True
    try:
        runner.start_stage(1, "crawl")
    except RuntimeError as exc:
        assert "already has" in str(exc)
    else:
        raise AssertionError("second start was accepted")
    finally:
        runner.RUNS.clear()
