# Model Lab Architecture

Model Lab is a local-first training framework. The repository contains one canonical data/training pipeline, a localhost FastAPI control plane, an optional Windows/Tk desktop surface, configuration, tests, and release tooling. Runtime datasets, checkpoints, logs, scratch state, credentials, and native build products are not part of the source-tree contract.

## System flow

```text
dataset groups / source configuration
              |
            crawl
              |
            clean
              |
      exact + semantic dedup
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
              |
       HF / GGUF / Ollama
```

The pipeline is implemented once in `pipeline/orchestrator.py`. `pipeline/app.py` exists as a backward-compatible import surface and delegates to the canonical orchestrator rather than implementing a second pipeline.

Each stage has a persisted artifact boundary. Hashes, manifests, dataset identity, and provenance determine whether an existing artifact can safely be reused.

## Repository layers

### `pipeline/`

Production data and training behavior:

- `crawler/`: source adapters, acquisition policy, bounded crawling, and source manifests
- `cleaner/` and `filtering/`: normalization, quality, and refusal filtering
- `embedder/` and `dedupe/`: semantic and compatibility deduplication
- `weighter/`: source/content balancing
- `tokenizer/`: BPE tokenizer training and reload
- `shardwriter/`: binary shard generation and manifests
- `trainer/`: Llama-style decoder-only model, training loop, evaluation, checkpoints, and resume
- `integrity.py`: SHA-256 hashing, manifests, validation, and atomic artifact handling
- `dataset_identity.py`: dataset-session identity validation
- `model_sizer.py`: hardware-aware training profile selection
- `orchestrator.py`: stage sequencing, resume boundaries, and artifact chaining
- `contracts/`: shared compatibility contracts

The canonical document flowing through the preprocessing stages is `pipeline.types.Document`. Compatibility namespaces delegate to the canonical contract instead of defining competing document schemas.

### `command_center/`

Local FastAPI control plane. It manages dataset sessions, credentials, process lifecycle, stage execution, API routes, system status, and crawler telemetry.

The command center stores dataset session state under the runtime dataset root and launches the canonical `run_pipeline.py` entry point for individual stages. It does not contain a separate training implementation.

The API is localhost-only. Mutating API requests require a custom control header and local-origin checks. File ingestion is confined to `imports/` and rejects absolute paths, traversal, and symlink sources. Log access is restricted to approved runtime roots.

### `ui/`

Optional Windows/Tk presentation and control surface. It calls the localhost command center and does not reimplement pipeline stages or artifact logic.

### `config/`

Checked-in configuration, dataset groups/profiles, source definitions, starter/smoke/full pipeline profiles, weighting and cleaning policies, and templates.

### `scripts/`

Bootstrap, environment reconciliation, export, GGUF, hardware, security, dataset-contract, evidence, and release-verification tooling.

### `tests/`

Automated contract, regression, security, coverage, release, and machine-boundary tests.

## Data and artifact boundaries

A dataset session is isolated under the runtime dataset root. The command center creates session directories with raw, logs, errors, output, and scratch areas.

Stage outputs carry hashes and provenance. Resume logic validates persisted artifacts before skipping a stage. Corrupt, incomplete, or mismatched artifacts are rebuilt or rejected.

Training checkpoints retain:

- model and training configuration identities
- shard and source-manifest identities
- seed
- optimizer/scaler state
- Python/NumPy/PyTorch RNG state
- train/validation loader state
- checkpoint SHA-256 manifest

Export refuses to proceed when the checkpoint, tokenizer, weighted corpus, shard manifest, source manifest, configuration, or model vocabulary identities do not agree.

## Model architecture

The built-in model is a Llama-style decoder-only transformer implemented in `pipeline/trainer/model.py`.

It contains:

- tied input embeddings and language-model head
- RMSNorm
- causal self-attention with grouped-query support
- RoPE positional encoding
- SwiGLU feed-forward blocks
- configurable dropout and model geometry
- presets for approximately 85M, 117M, and 360M parameters

Training is implemented in `pipeline/trainer/train.py` with gradient accumulation, evaluation, cosine learning-rate scheduling, checkpointing, deterministic state capture, and optional hardware-aware sizing.

## CLI and runtime entrypoints

`run_pipeline.py` is the canonical CLI. It exposes:

- `--doctor`
- `--hardware-report`
- `--list-stages`
- `--list-groups`
- `--stages`
- `--dataset-group`
- `--dataset-id`
- `--no-resume`
- `--web`

`bootstrap.py` owns dependency installation, host preflight, hardware detection, PyTorch channel selection, and native-toolchain reconciliation.

`run_command_center.py` launches the FastAPI control plane directly. `launch.py` starts the desktop control surface.

## Configuration and starter behavior

The canonical starter profile is `config/pipeline_config.yaml`. It enables crawl, clean, semantic deduplication, weighting, tokenization, sharding, and a bounded training run. Export is disabled in the starter profile and must be enabled or invoked through an appropriate release/export workflow.

The full profile is selected explicitly. Dataset-specific sessions use the configured dataset identity/profile system.

## Native export boundary

llama.cpp is not vendored. The repository reconciles a pinned checkout under `third_party/llama.cpp/` when native conversion or inference verification is required.

The export path:

1. validates checkpoint and upstream provenance;
2. maps the internal model state to a Hugging Face-compatible Llama checkpoint;
3. converts the checkpoint to F16 GGUF;
4. optionally quantizes to a supported GGUF format;
5. writes export metadata and dataset/model cards;
6. validates the final GGUF through native llama.cpp inference during the full native release gate.

## Runtime boundaries

CI can verify Python behavior, configuration contracts, artifact logic, and automated tests. CUDA, native llama.cpp behavior, network-dependent acquisition, desktop rendering, and target deployment hardware remain environment-dependent.

The code and workflow definitions are authoritative for exact commands and behavior. This document describes the architecture, not a promise that every environment-specific capability is available everywhere.

## Extension rules

1. Add new sources through crawler adapters and configuration.
2. Add cleaning/filtering behavior through existing pipeline layers.
3. Preserve the canonical `Document` contract.
4. Preserve dataset identity, manifests, hashes, and provenance at stage boundaries.
5. Keep optional heavy dependencies lazy where practical.
6. Keep credentials, runtime data, checkpoints, caches, and generated logs outside source control.
7. Preserve the single canonical implementation for each pipeline responsibility.

## Release principle

A production release is a source state plus current evidence. Automated tests, native verification, target-machine checks, dataset/source-rights review, and production operational evidence must be distinguished rather than inferred from one another.
