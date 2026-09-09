# Model Lab — Project State

**Version:** 1.3.0

## Identity

- Package: **Model Lab**
- System: **M²S Model Training Pipeline**
- `bootstrap.py`: environment installation and environment preflight (`--install`, `--doctor`)
- `run_pipeline.py` / `mlab`: canonical pipeline CLI and project/runtime readiness doctor
- `launch.py`: desktop UI launcher
- `run_command_center.py`: backend-only command-center launcher
- Pipeline: crawl → clean → dedup → weight → tokenize → shard → train → export

## Seeded dataset groups

1. `swe_cs_systems` — Software Engineering + CS + Systems
2. `ai_ml_cybersec_dataeng` — AI/ML + Cybersecurity + Data Engineering
3. `sci_reasoning_forensics_formal` — Scientific Reasoning + Forensics + Formal Methods
4. `domain_finance_bio_robotics` — Finance + Biology + Robotics

## Architecture

The desktop UI is a control surface, not a second pipeline implementation. Dataset state, stage execution, credentials, and runtime behavior are owned by the existing backend.

## Diagnostics

`bootstrap.py --doctor` checks the host environment and installation prerequisites without running pipeline stages. `run_pipeline.py --doctor` checks project/runtime readiness; `--hardware-report` adds conservative host-specific training guidance. These are complementary checks, not competing preflight systems.

## Native dependency

llama.cpp is not a vendored source tree in the public repository. The supported native revision is bootstrapped separately when GGUF conversion or quantization is required.

## Verification

The release process separates automated contract/behavior tests, Python/static checks, target-machine environment checks, and human-visible desktop acceptance. Generated datasets, logs, caches, checkpoints, and model artifacts are not source-controlled.
