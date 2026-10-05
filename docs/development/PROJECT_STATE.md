# Model Lab Project State

**Package version:** 1.3.0  
**Release posture:** release-candidate hardening  
**Source of truth:** the Git branch and commit currently under review; after merge, `main` is the authoritative public branch.

## Identity

- Package: **Model Lab**
- System: **M²S Model Training Pipeline**
- Python package requirement: **>=3.11,<3.15**
- `bootstrap.py`: dependency installation, host preflight, hardware detection, PyTorch channel selection, and native-toolchain reconciliation
- `run_pipeline.py`: canonical pipeline CLI and project/runtime doctor
- `run_command_center.py`: direct FastAPI command-center launcher
- `launch.py`: optional Windows/Tk desktop launcher
- Pipeline: crawl → clean → semantic dedup → weight → tokenize → shard → train → export

## Dataset catalog

The canonical configuration defines ten dataset groups:

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

Dataset sessions retain canonical dataset/group identity and isolate raw, logs, errors, output, and scratch state.

## Canonical architecture

The source has one production orchestrator in `pipeline/orchestrator.py`. Compatibility modules delegate to it rather than implementing parallel stage logic.

The pipeline stages are:

1. crawl
2. clean
3. semantic dedup
4. weight
5. tokenize
6. shard
7. train
8. export

The canonical data contract is `pipeline.types.Document`. Stage artifacts carry hashes and provenance so resume can reject stale or mismatched state.

The built-in model is a Llama-style decoder-only transformer implemented in `pipeline/trainer/model.py`, with 85M, 117M, and 360M presets. Training captures deterministic state and checkpoint provenance.

## Control plane

The FastAPI command center in `command_center/` provides:

- dataset creation/listing/status
- dataset ingestion
- individual stage execution and stop control
- dataset-group discovery
- credential set/list/test/delete
- crawler statistics, domain telemetry, and log access
- local system/runtime status

The command center launches the canonical `run_pipeline.py` process for stage execution. It is localhost-only, requires a control header for mutations, and applies filesystem confinement to ingestion and log access.

The optional Tk UI in `ui/` is a presentation/control surface over this backend. It is not a second pipeline.

## Diagnostics

- `bootstrap.py --doctor`: installation and host prerequisites
- `run_pipeline.py --doctor`: project/runtime readiness
- `run_pipeline.py --doctor --hardware-report`: adds conservative host-specific training guidance
- `run_pipeline.py --list-stages`: lists pipeline stages
- `run_pipeline.py --list-groups`: lists configured dataset groups

Diagnostics do not execute pipeline stages.

## Release controls

Current source-level controls include:

- Python packaging/bootstrap support for 3.11 through 3.14
- Linux and Windows CI coverage for Python 3.11 and 3.14
- PowerShell bootstrap contract validation
- Ruff and Python compilation
- **90% enforced aggregate pytest coverage**
- security and dependency auditing
- dataset identity, artifact integrity, and provenance contracts
- deterministic checkpoint/resume validation
- pinned llama.cpp bootstrap
- Hugging Face/GGUF export and native inference verification
- dependency freeze and SBOM generation
- release evidence packaging

## Release boundary

Source readiness is not the same as release approval.

A release requires current evidence for the exact approved commit, including successful automated gates and the required native/target-environment evidence. Production training, dataset rights/provenance review, and target deployment validation remain operational gates.

Historical reports remain audit history and do not override current code or workflow results.

## Native dependency

llama.cpp is not vendored. The repository bootstraps the configured pinned revision under `third_party/llama.cpp/` when native conversion, quantization, or inference verification is required.

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
