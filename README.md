# ML-Framework

**ML-Framework** is the public source repository for **Model Lab**, the **M²S Model Training Pipeline**: a local-first system for acquiring and validating training data, preparing artifacts, training a Llama-style decoder-only model, and exporting it for local inference.

The source tree contains one canonical pipeline implementation, a localhost FastAPI control plane, an optional Windows/Tk desktop surface, tests, security controls, and release tooling. Runtime datasets, checkpoints, logs, caches, credentials, and native build products are outside the source-tree contract.

## What it does

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

The repository includes:

- dataset groups, source configuration, and dataset-session identity
- source scoring, URL security, bounded acquisition, filtering, and provenance manifests
- exact and semantic near-deduplication
- deterministic BPE tokenizer training and validated binary shard generation
- hardware-aware training profiles and checkpoint integrity/resume state
- a Llama-style decoder-only transformer with 85M, 117M, and 360M presets
- Hugging Face checkpoint mapping, GGUF export, quantization, and native llama.cpp verification
- localhost FastAPI command center for dataset lifecycle, stage control, credentials, telemetry, and system status
- optional Windows/Tk desktop control surface that delegates to the command center
- automated contract, regression, security, coverage, and release verification

## Repository map

```text
ML-Framework/
├── README.md
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
├── pyproject.toml
├── bootstrap.py
├── run_pipeline.py
├── run_command_center.py
├── launch.py
├── command_center/
├── config/
├── pipeline/
├── ui/
├── scripts/
├── tests/
└── docs/
```

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Start Here](docs/development/START_HERE.md)
- [Project State](docs/development/PROJECT_STATE.md)
- [Dataset Provenance and Source Policy](docs/development/DATA_PROVENANCE.md)
- [Source of Truth](docs/development/SYNC_SOURCE_OF_TRUTH.md)
- [Release Checklist](docs/release/RELEASE_CHECKLIST.md)
- [Release Readiness](docs/release/RELEASE_READINESS_PLAN.md)
- [Release Verification](docs/release/RELEASE_VERIFICATION_REPORT.md)
- [Build Manifest](docs/release/BUILD_MANIFEST.json)
- [Static Pipeline Audit](docs/release/static_pipeline_audit.md)
- [Verification](docs/verification/VERIFICATION.md)
- [Verification Checklist](docs/verification/VERIFICATION_CHECKLIST.md)
- [Export and llama.cpp Integration](docs/EXPORT_AND_LLAMA_CPP_INTEGRATION.md)

Historical reports are retained as history. They are not current status documents.

## Quick start

### Windows PowerShell

```powershell
python .\bootstrap.py --install
python .\bootstrap.py --doctor
python .\run_pipeline.py --no-resume
```

### Linux / macOS / Termux

```bash
python3 bootstrap.py --install
python3 bootstrap.py --doctor
python3 run_pipeline.py --no-resume
```

The project supports **Python 3.11 through 3.14**. Python 3.15+ is outside the declared package/bootstrap range.

The canonical starter profile is `config/pipeline_config.yaml`. It is intentionally bounded for correctness checks. The larger `config/pipeline_config.full.yaml` profile must be selected explicitly.

The bootstrapper installs framework dependencies and defaults to the official CUDA PyTorch wheel index. CPU-only hosts can select `--torch-channel cpu`; `--torch-channel default` uses the standard PyPI channel.

## Runtime architecture

The pipeline has eight canonical stages:

1. **crawl**: acquire configured sources into a dataset session and produce source/provenance metadata
2. **clean**: normalize, filter, and perform exact duplicate removal
3. **dedup**: semantic near-deduplication using the configured embedding/index strategy
4. **weight**: apply source/content weighting
5. **tokenize**: train or reload the configured BPE tokenizer
6. **shard**: create validated binary training shards and a shard manifest
7. **train**: train the configured Llama-style decoder-only model and write integrity-protected checkpoints
8. **export**: validate lineage, map the checkpoint to Hugging Face format, convert to GGUF, optionally quantize, and write export evidence

Artifacts are chained through hashes and provenance. Resume logic validates those identities before reusing persisted output. Dataset IDs and dataset-group identities are preserved across command-center sessions and pipeline execution.

## Control plane and desktop

The FastAPI command center is localhost-only. Mutating API requests require the command-center control header and local-origin rules. Dataset ingestion is confined to the configured imports directory and rejects absolute paths, traversal, and symlink sources.

The desktop UI is a control surface, not a second pipeline implementation. It delegates pipeline actions to the existing localhost command center. The 1760×990 value is a desktop verification target, not a universal requirement.

Launch the desktop surface with:

```powershell
python .\launch.py
```

Run the backend without opening a browser:

```powershell
python .\run_command_center.py --no-browser
```

The pipeline CLI can also start the backend with `python run_pipeline.py --web`.

## Verification

Static:

```bash
python scripts/verify_release.py
```

Full native release verification:

```bash
python scripts/verify_release.py --bootstrap-native
```

The static command covers compilation, Ruff, pytest/coverage, and the required project doctor. The native command additionally bootstraps the pinned llama.cpp toolchain and runs the deterministic local export/inference fixture.

The repository enforces **90% aggregate pytest coverage** through `pyproject.toml`.

## Security and release evidence

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
python scripts/generate_release_evidence.py
```

The security gate checks tracked source, dependency consistency, and dependency vulnerabilities. Release evidence records dependency state and SBOM information.

## GitHub Actions

The repository has three workflows:

- **CI**: Linux and Windows on Python 3.11 and 3.14, bootstrap/doctor contracts, dependency consistency, Ruff, compilation, tests/coverage, and Windows PowerShell bootstrap validation.
- **Security**: security gate on pushes and pull requests, plus manual dispatch.
- **Release Gate**: security, release evidence, target-hardware/native verification, package build, and evidence upload.

Workflow files and current Actions results are authoritative for status. This README deliberately does not hard-code a green/red result.

## Native llama.cpp boundary

Native llama.cpp is pinned and bootstrapped separately. GGUF conversion requires `convert_hf_to_gguf.py`; quantized export additionally requires `llama-quantize`. The repository also validates the exported GGUF through `llama-cli` during the full native release fixture.

Historical Termux evidence demonstrates native tool execution on Android 16/aarch64. It is not a complete end-to-end release result.

## Release boundary

The source tree does not by itself prove that:

- a production dataset has been legally approved;
- a useful model has converged;
- target deployment hardware has passed native inference;
- a production training run has completed;
- the exact approved commit has passed every required release gate.

Those are execution and operational facts and must be backed by current evidence.
