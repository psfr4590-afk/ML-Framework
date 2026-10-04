# ML-Framework

**ML-Framework** is the public source repository for **Model Lab**, the **M²S Model Training Pipeline**: an end-to-end, local-first system for building training datasets, training a model, and exporting it for local inference.

The repository is under release-candidate hardening. The source tree contains the pipeline, control plane, optional desktop surface, tests, security controls, and release tooling. A production release is not claimed until the required evidence exists for the exact approved commit.

## What it does

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

The repository includes:

- dataset groups and crawl configuration
- source scoring, URL security, filtering, and provenance manifests
- exact and semantic deduplication
- deterministic tokenizer and validated binary shard generation
- isolated dataset sessions and resumable stage boundaries
- hardware-aware training profiles and checkpoint integrity
- GGUF export and native llama.cpp verification tooling
- localhost FastAPI command center and optional Windows/Tk desktop surface
- automated contract, regression, security, and release tests

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

The canonical starter profile is `config/pipeline_config.yaml`. It is bounded and CPU-safe. The larger `config/pipeline_config.full.yaml` profile must be selected explicitly.

The bootstrapper installs framework dependencies and uses the official CUDA PyTorch wheel index by default. CPU-only hosts can use `--torch-channel cpu`; `--torch-channel default` uses the standard PyPI channel.

## Runtime behavior

The pipeline is linear by design. Each stage consumes a verified artifact and produces a new artifact with hashes and provenance. Invalid or mismatched artifacts are rebuilt or rejected instead of silently reused.

Training checkpoints retain model/optimizer state, deterministic RNG and loader state, and provenance identities. Export verifies checkpoint, tokenizer, weighted-corpus, shard, source-manifest, configuration, seed, and provenance identities before conversion.

## Desktop and backend

```powershell
python .\launch.py
python .\run_command_center.py --no-browser
```

The desktop UI calls the localhost FastAPI command center and does not implement a second pipeline. The 1760×990 value is a desktop verification target, not a universal requirement.

## Verification

Static:

```bash
python scripts/verify_release.py
```

Full native release verification:

```bash
python scripts/verify_release.py --bootstrap-native
```

The static command covers compilation, Ruff, pytest/coverage, and the required doctor. The native command additionally bootstraps the pinned llama.cpp toolchain and runs the deterministic local export/inference fixture.

The repository enforces **90% aggregate pytest coverage**.

## Security and release evidence

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
python scripts/generate_release_evidence.py
```

The security gate checks tracked source, dependency consistency, and dependency vulnerabilities. Release evidence records dependency state and SBOM information.

## GitHub Actions

The repository has three workflows:

- **CI**: Linux and Windows on Python 3.11 and 3.14, bootstrap doctor, dependency consistency, Ruff, compilation, tests/coverage, and the Windows PowerShell bootstrap contract.
- **Security**: security gate on pushes and pull requests, plus manual dispatch.
- **Release Gate**: security, release evidence, target-hardware/native verification, package build, and evidence upload.

Workflow files and current Actions results are authoritative for status. This README deliberately does not hard-code a green/red result.

## Native llama.cpp boundary

Native llama.cpp is pinned and bootstrapped separately. GGUF conversion requires `convert_hf_to_gguf.py`; quantized export additionally requires `llama-quantize`.

Historical Termux evidence demonstrates native tool execution on Android 16/aarch64. It is not a complete end-to-end release result.

## Release boundary

The source tree does not by itself prove that:

- a production dataset has been legally approved;
- a useful model has converged;
- target deployment hardware has passed native inference;
- a production training run has completed;
- the exact approved commit has passed every required release gate.

Those are execution and operational facts and must be backed by current evidence.