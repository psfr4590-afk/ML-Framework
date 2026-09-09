# ML-Framework

**ML-Framework** is the public source repository for **Model Lab**, the M²S end-to-end model training pipeline.

This project is the result of a deliberately hardened build process. The goal is not another demo notebook or a collection of disconnected ML scripts. It is a reproducible path from seeded data sources to a locally usable trained model.

## What it does

The canonical pipeline is:

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

The repository includes:

- pre-seeded dataset groups and crawl URLs
- source-quality scoring and domain/content weighting
- HTML/unicode cleaning and refusal/assistant-contamination filtering
- exact and semantic near-duplicate handling
- deterministic tokenizer and binary shard generation
- isolated dataset sessions for independent experiments
- hardware/CUDA readiness checks
- local training and checkpoint management
- GGUF export for local inference
- a localhost FastAPI command center and desktop control surface
- contract, regression, structure, and machine-environment tests
- release verification tooling

## Seeded dataset groups

Four dataset groups are preconfigured:

- `swe_cs_systems` — software engineering, computer science, and systems
- `ai_ml_cybersec_dataeng` — AI/ML, cybersecurity, and data engineering
- `sci_reasoning_forensics_formal` — scientific reasoning, forensics, and formal methods
- `domain_finance_bio_robotics` — finance, biology, robotics, and related domains

General web seeds live in `config/seed_urls.txt`.

## Quick start

From the repository root on Windows:

```powershell
pip install -r .\requirements.txt
python .\run_pipeline.py --doctor
python -m pytest -q
python .\launch.py
```

For a non-destructive release check:

```powershell
python .\scripts\verify_release.py
```

The release verifier explicitly distinguishes automated checks from target-machine checks. A skipped hardware check is not reported as a fake pass.

## Dataset sessions

Dataset sessions isolate mutable output so separate experiments do not trample one another's artifacts. When a dataset session exists, run the pipeline against it with `--dataset-id`.

Example:

```powershell
python .\run_pipeline.py --config .\config\pipeline_config.yaml --dataset-id 5
```

## Configuration

The main configuration is `config/pipeline_config.yaml`. Smoke-test settings live in `config/pipeline_config.smoke.yaml` and `config/dataset_groups.smoke.yaml`.

Credentials are supplied through environment variables. Example metadata is provided in `config/credentials.example.yaml`. Secret values are intentionally absent from the repository.

## Local-first design

Model Lab is designed around local execution. Optional remote services are used as data sources or enrichment inputs where configured, while generated datasets, checkpoints, model artifacts, caches, logs, and native build products remain runtime state rather than source-control payloads.

## Repository hygiene

The public repository intentionally excludes:

- generated datasets and scratch data
- checkpoints and model weights
- GGUF/model binaries
- Python caches and test caches
- local logs and runtime state
- secrets and credential material
- native build products

The supplied delivery archive contains those runtime artifacts for reproducibility, but they do not belong in the source repository.

## Status

The source of truth for the current implementation is the validated Model Lab 1.3.0 delivery used to populate this repository. Release verification remains a combination of automated tests, environment checks, and human-visible desktop acceptance.
