# Model Lab Architecture

Model Lab is a local-first training framework. The repository contains source, configuration, tests, release tooling, and the optional desktop/control surfaces. Runtime datasets, checkpoints, logs, scratch state, and native build products are not part of the source-tree contract.

## System flow

```text
seed URLs / dataset groups
        |
      crawl
        |
      clean
        |
  semantic dedup
        |
      weight
        |
    tokenize
        |
      shard
        |
      train
        |
     export
```

Each stage has a persisted artifact boundary. Integrity and provenance metadata are used to decide whether an existing artifact can safely be reused.

## Repository layers

### `pipeline/`

Production data and training behavior:

- `crawler/`: source adapters and acquisition policy
- `cleaner/` and `filtering/`: normalization and quality/refusal filtering
- `embedder/` and `dedupe/`: semantic and compatibility deduplication
- `weighter/`: corpus balancing
- `tokenizer/`: tokenizer training and reload
- `shardwriter/`: binary shard generation and manifests
- `trainer/`: model definition, training, checkpointing, and resume
- `integrity.py`: hashes, manifests, validation, and atomic artifact handling
- `model_sizer.py`: hardware-aware profile selection
- `orchestrator.py`: stage sequencing, resume boundaries, and artifact chaining
- `contracts/`: shared compatibility contracts

### `command_center/`

Local FastAPI control plane for dataset sessions, credentials, process lifecycle, API routes, and crawler telemetry.

### `ui/`

Optional Windows/Tk presentation and control surface. It calls the command center and does not reimplement pipeline stages.

### `config/`

Checked-in pipeline configuration, dataset groups, source definitions, starter/smoke/full profiles, and templates.

### `scripts/`

Bootstrap, environment, export, GGUF, hardware, security, and release-verification tooling.

### `tests/`

Automated contract, regression, release, security, and machine-boundary tests.

## Runtime boundaries

CI can verify Python behavior, configuration contracts, artifact logic, and automated tests. CUDA, native llama.cpp behavior, network-dependent acquisition, desktop rendering, and target deployment hardware are environment-dependent.

The code and workflow definitions are authoritative for exact commands and behavior. This document describes the architecture, not a promise that every environment-specific capability is available everywhere.

## Data and artifact isolation

Dataset sessions use isolated runtime paths. Stage outputs carry hashes and provenance. Resume logic validates persisted artifacts before skipping a stage. Corrupt, incomplete, or mismatched artifacts are rebuilt or rejected.

Training checkpoints include deterministic state and provenance identities needed for safe resume.

## Extension rules

1. Add new sources through crawler adapters.
2. Add cleaning/filtering behavior through the existing pipeline layers and configuration.
3. Preserve the canonical document contract.
4. Treat manifests and hashes as part of stage contracts.
5. Keep optional heavy dependencies lazy where practical.
6. Never commit runtime credentials, datasets, checkpoints, caches, or generated logs.

## Release principle

A production release is a source state plus current evidence. Automated tests, native verification, target-machine checks, and production operational evidence must be distinguished rather than inferred from one another.