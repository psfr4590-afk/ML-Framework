# SQLite experiment store

Model Lab now keeps a structured SQLite source of truth alongside the existing raw run artifacts.

## Contract

`output/experiment.db` records experiments, runs, datasets, sources, source statistics, stages, artifacts, checkpoints, metrics, evaluations, hardware, configuration identities, warnings, errors, and runtime estimates.

The JSON run manifest and raw logs remain forensic evidence. The SQLite store does not replace them, and the system does not automatically delete experiments or raw evidence.

The durable identity chain is:

`experiment -> run -> dataset/config/hardware -> stages -> artifacts`

Artifacts retain SHA-256 values and paths so the structured record can be checked against retained evidence.

## Querying

```python
from pathlib import Path
from pipeline.experiment_db import ExperimentDB

db = ExperimentDB(Path("output/experiment.db"))
print(db.search_runs(status="PASS"))
print(db.get_run("run-id"))
print(db.lineage("run-id"))
print(db.compare_runs("run-a", "run-b"))
db.close()
```

The store is created automatically when a pipeline run tracker is initialized. Every run-manifest update is synchronized into SQLite, so an interrupted run still leaves queryable state.

## Evidence boundary

SQLite describes what Model Lab knows about the run. Raw manifests, logs, checkpoints, dataset artifacts, and other retained files preserve what the system actually observed. Neither silently replaces the other.

This is an observability and reproducibility store, not a claim that a dataset, model, or training run is production-ready.
