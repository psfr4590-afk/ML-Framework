# Model Lab — Project State

**Version:** 1.3.0

## Identity

- Package: **Model Lab**
- System: **M²S Model Training Pipeline**
- Launcher: `launch.py`
- Backend: localhost FastAPI command center
- Pipeline: crawl → clean → dedup → weight → tokenize → shard → train → export

## Seeded dataset groups

1. `swe_cs_systems` — Software Engineering + CS + Systems
2. `ai_ml_cybersec_dataeng` — AI/ML + Cybersecurity + Data Engineering
3. `sci_reasoning_forensics_formal` — Scientific Reasoning + Forensics + Formal Methods
4. `domain_finance_bio_robotics` — Finance + Biology + Robotics

## Architecture

The desktop UI is a control surface, not a second pipeline implementation. Dataset state, stage execution, credentials, and runtime behavior are owned by the existing backend.

## Verification

The release process separates automated contract/behavior tests, Python/static checks, target-machine environment checks, and human-visible desktop acceptance. Generated datasets, logs, caches, and model artifacts are not source-controlled.
