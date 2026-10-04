# Model Lab Project State

**Package version:** 1.3.0  
**Release posture:** release-candidate hardening  
**Source of truth:** the Git branch and commit currently under review; after merge, `main` is the authoritative public branch.

## Identity

- Package: **Model Lab**
- System: **M²S Model Training Pipeline**
- `bootstrap.py`: dependency installation and host preflight
- `run_pipeline.py` / `mlab`: pipeline CLI and project/runtime doctor
- `launch.py`: desktop launcher
- `run_command_center.py`: backend-only launcher
- Pipeline: crawl → clean → semantic dedup → weight → tokenize → shard → train → export

## Dataset catalog

The checked-in configuration contains ten dataset groups:

1. `swe_cs_systems`
2. `ai_ml_cybersec_dataeng`
3. `sci_reasoning_forensics_formal`
4. `domain_finance_bio_robotics`
5. `math_statistics_optimization`
6. `physics_chemistry_materials`
7. `biomedical_health_science`
8. `law_compliance_governance`
9. `linguistics_information_retrieval`
10. `climate_energy_geospatial`

## Diagnostics

- `bootstrap.py --doctor`: installation and host prerequisites
- `run_pipeline.py --doctor`: project/runtime readiness
- `run_pipeline.py --doctor --hardware-report`: adds conservative hardware guidance
- `run_pipeline.py --list-stages`: lists pipeline stages
- `run_pipeline.py --list-groups`: lists configured dataset groups

Diagnostics do not execute pipeline stages.

## Architecture

The desktop UI is a control surface, not a second pipeline implementation. Pipeline behavior stays in `pipeline/`; backend behavior stays in `command_center/`.

Runtime datasets, checkpoints, GGUF artifacts, caches, logs, live credentials, and native build products are not part of the source-tree contract.

## Release controls

Current source-level controls include:

- Linux and Windows CI on Python 3.11 and 3.14
- PowerShell bootstrap contract validation
- Ruff and Python compilation
- **90% enforced aggregate pytest coverage**
- security and dependency auditing
- artifact integrity and provenance contracts
- deterministic checkpoint/resume validation
- pinned llama.cpp bootstrap
- GGUF export and native inference verification
- dependency freeze and SBOM generation
- release evidence packaging

## Release boundary

Source readiness is not the same as release approval.

A release requires current evidence for the exact approved commit, including successful automated gates and the required native/target-environment evidence. Production training and production dataset rights/provenance review remain operational gates.

Historical reports remain audit history and do not override current code or workflow results.

## Native dependency

llama.cpp is not vendored. The repository bootstraps the configured pinned revision when native conversion, quantization, or inference verification is required.

Historical Android 16/aarch64 quantizer evidence remains useful tool-level evidence. It does not establish that the current source commit has passed the complete native release gate.

## Repository hygiene

Keep runtime outputs outside the source contract:

- datasets
- output artifacts
- scratch data
- checkpoints
- logs
- caches
- native build products
- live credentials and `.env` files
