# ML-Framework

**ML-Framework** is the public source repository for **Model Lab**, the **M²S Model Training Pipeline**: an end-to-end, local-first system for building training datasets, training a model, and exporting it for local inference.

The repository is at **release-candidate (RC) source readiness**. The implementation, contracts, regression coverage, security/reproducibility controls, release tooling, and native GGUF verification path are in the repository. The latest `main` commit has passed Linux CI, Windows CI, Security, and CodeQL; the native release gate remains a separate execution-dependent requirement before a production release is claimed.

**Termux native-toolchain evidence (2026-09-29):** on Android 16 / aarch64, the pinned llama.cpp checkout at `b95502b...` was configured and built successfully through the `llama-quantize` target. The resulting Android ELF executable was started successfully and its help output enumerated the supported quantization types. This verifies the native quantizer itself on that target; it does **not** replace the complete Python release gate or an end-to-end Model Lab export/inference run.

## RC status

**Current branch:** `main`  
**Automated gate state:** latest `main` CI, Security, and CodeQL checks are green.  
**Package version:** `1.3.0`  
**PRs #22 and #24:** merged

The repository has completed the current hardening and regression-repair work represented by those merges. The remaining release evidence is execution-dependent, not a missing implementation contract:

- the native release gate must complete successfully for the exact release commit;
- `python scripts/verify_release.py --bootstrap-native` must complete successfully;
- the resulting GGUF must pass native llama.cpp inference validation;
- the final release evidence must retain dependency freeze, SBOM, provenance, export, integrity, and inference records;
- production training remains a separate operational run and is not implied by the bounded RC smoke test.

A green static test suite alone is not a production-release claim.

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
- hardware/CUDA readiness checks and conservative hardware-aware training profiles
- local training and checkpoint management
- GGUF export for local inference
- a localhost FastAPI command center and desktop control surface
- contract, regression, structure, and machine-environment tests
- security and dependency auditing
- deterministic release verification and native GGUF/inference validation tooling
- release evidence generation, including dependency freeze and SBOM output

## Repository map

The root is intentionally kept small. Runtime code, configuration, scripts, tests, and UI live in their functional directories. Engineering history, audits, release material, and verification records live under `docs/` rather than competing with the project entry points.

```text
ML-Framework/
├── README.md              # Start here
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
├── pyproject.toml         # Package metadata
├── bootstrap.py           # Canonical environment setup
├── run_pipeline.py        # Pipeline entry point
├── run_command_center.py  # Command center entry point
├── command_center/        # Local API/control backend
├── config/                # Starter, smoke, full, and dataset configs
├── pipeline/              # Crawl → export implementation
├── ui/                    # Desktop control surface
├── scripts/               # Native/bootstrap/release tooling
├── tests/                 # Automated verification
└── docs/                  # Architecture, development, release, verification
```

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Start Here](docs/development/START_HERE.md)
- [Project State](docs/development/PROJECT_STATE.md)
- [Dataset Provenance and Source Policy](docs/development/DATA_PROVENANCE.md)
- [Source of Truth](docs/development/SYNC_SOURCE_OF_TRUTH.md)
- [SQLite Experiment Store](docs/development/EXPERIMENT_STORE.md)
- [Release Checklist](docs/release/RELEASE_CHECKLIST.md)
- [Release Readiness](docs/release/RELEASE_READINESS_PLAN.md)
- [Release Verification](docs/release/RELEASE_VERIFICATION_REPORT.md)
- [Build Manifest](docs/release/BUILD_MANIFEST.json)
- [Static Pipeline Audit](docs/release/static_pipeline_audit.md)
- [Audit Report](docs/verification/AUDIT_REPORT.md)
- [Verification](docs/verification/VERIFICATION.md)
- [Verification Checklist](docs/verification/VERIFICATION_CHECKLIST.md)

## Seeded dataset groups

Ten dataset groups are preconfigured:

- `swe_cs_systems` — software engineering, computer science, and systems
- `ai_ml_cybersec_dataeng` — AI/ML, cybersecurity, and data engineering
- `sci_reasoning_forensics_formal` — scientific reasoning, forensics, and formal methods
- `domain_finance_bio_robotics` — finance, biology, and robotics
- `math_statistics_optimization` — mathematics, statistics, and optimization
- `physics_chemistry_materials` — physics, chemistry, and materials science
- `biomedical_health_science` — biomedical science, bioinformatics, and health research
- `law_compliance_governance` — law, compliance, and digital governance
- `linguistics_information_retrieval` — linguistics, NLP, and information retrieval
- `climate_energy_geospatial` — climate science, energy systems, and geospatial analysis

General web seeds live in `config/seed_urls.txt`.

## Quick start

There is exactly one canonical first-run path. From the project root, install with the bootstrapper, verify the environment, then run the default starter profile.

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

`config/pipeline_config.yaml` is the single canonical starter profile used when no `--config` argument is supplied. It is deliberately bounded, CPU-safe, and exercises the real pipeline and artifact chain without starting a long production training job.

The larger profile is preserved as `config/pipeline_config.full.yaml` and must be selected explicitly for large runs.

The bootstrapper installs framework dependencies first, then installs PyTorch from the official CUDA wheel index by default. CPU-only hosts can explicitly use `python bootstrap.py --install --torch-channel cpu`, while `--torch-channel default` uses the standard PyPI PyTorch channel.

After the starter run succeeds, inspect the host before doing expensive work:

```powershell
python .\run_pipeline.py --doctor --hardware-report
```

or:

```bash
python3 run_pipeline.py --doctor --hardware-report
```

## What happens during a run

The normal pipeline is intentionally linear:

`crawl → clean → dedup → weight → tokenize → shard → train → export`

Each stage reads a verified artifact from the previous stage and writes a new artifact with a manifest containing provenance and hashes. If an existing artifact does not match the expected provenance or integrity data, it is rebuilt instead of being silently reused.

Training checkpoints persist the model, optimizer, scaler, global RNG state, train/validation shard order, shard cursor, and loader RNG state. Resume therefore continues from the same data position instead of merely restoring model weights.

Final export verifies the checkpoint, tokenizer, weighted corpus, shard manifest, source manifest, independent configuration identities, seed, and explicit artifact relationships before conversion. The historical pipeline-wide configuration hash is retained as legacy evidence but is no longer treated as the identity of every stage. A mismatch stops export rather than allowing an inconsistent artifact to be presented as a valid model.

For an independent, read-only lineage check, run `python scripts/validate_lineage.py --output-dir output --checkpoint <checkpoint.pt>`. It reports configuration, artifact, parent, checkpoint, and export relationships without rewriting historical evidence.

The starter profile is a correctness check, not a useful model-training run. For serious training, inspect the hardware report first and explicitly choose an appropriate larger configuration.

## Windows launch

After the first-run path is healthy:

```powershell
python .\launch.py
```

`launch.py` is the desktop entry point. It starts the existing desktop control surface, which uses the localhost FastAPI command center as its backend. The current desktop UI is documented for a 1760x990 target display; this is a machine/UI verification boundary, not a claim that every host has that display geometry.

Model Lab navigates the real pipeline and dataset sessions. It does not implement a second copy of the crawler, cleaner, deduplicator, tokenizer, sharder, trainer, or exporter.

## Backend-only mode

```powershell
python .\run_command_center.py --no-browser
```

Without `--no-browser`, the backend opens the localhost command center in the default browser after its health endpoint is ready. The command center binds to localhost by default.

## Release verification

Static verification:

```bash
python scripts/verify_release.py
```

This runs compilation, Ruff, the full test suite with coverage reporting, and the required project/runtime doctor. It deliberately does **not** claim native GGUF verification.

Full native RC/release verification:

```bash
python scripts/verify_release.py --bootstrap-native
```

The native gate additionally reconciles the pinned llama.cpp toolchain and runs a deterministic, network-free fixture through tokenization, sharding, training, GGUF export, export-card generation, GGUF integrity verification, and native llama.cpp inference.

A successful RC candidate should have this command pass before release approval.

## Security and release evidence

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
python scripts/generate_release_evidence.py
```

The security gate checks tracked source for common secret patterns, dependency consistency with `pip check`, and dependency vulnerabilities with `pip-audit`.

The release evidence generator records the resolved dependency environment and SBOM. The release workflow combines those records with the native release verification and uploads the resulting evidence artifact.

## GitHub Actions

The repository contains separate CI, security, and release workflows.

- CI covers Linux and Windows Python 3.11 and 3.14 environments, bootstrap doctor, dependency consistency, Ruff, compilation, tests/coverage, and the Windows PowerShell bootstrap contract.
- Security runs the repository security gate on `main` pushes and pull requests and can also be dispatched manually.
- Release runs the security gate, generates dependency/SBOM evidence, executes `verify_release.py --bootstrap-native`, and uploads release evidence. It is configured for manual dispatch and version tags.

The release workflow is manually dispatchable and tag-driven so the complete native gate can be run against the approved source before an RC is promoted.

## Production export requirement

Final GGUF export requires the pinned llama.cpp checkout containing `convert_hf_to_gguf.py`. Quantized exports also require the built `llama-quantize` executable. The exporter refuses to claim success when required tools are missing or when the training provenance chain is incomplete or inconsistent.

## Termux / Android native toolchain

Model Lab supports a headless Termux runtime for the pipeline and native GGUF export. The Tk desktop UI is intentionally not a dependency of the portable pipeline test suite.

To prepare the native llama.cpp toolchain after first-run validation:

```bash
bash scripts/bootstrap_llama_cpp.sh
python scripts/verify_release.py --bootstrap-native
```

The native bootstrap uses a reduced Android-safe build profile under Termux and builds only the required `llama-quantize` target. The Termux build is serialized to reduce memory pressure during compilation. The Python-side GGUF converter remains part of the pinned llama.cpp checkout. The current Termux evidence was produced with the native binary at `third_party/llama.cpp/build-model-lab/bin/llama-quantize`.

`sentence-transformers` and `faiss-cpu` are required runtime dependencies because semantic deduplication is a required pipeline capability. The default embedding model remains local-only; set `allow_model_download: true` only when an explicit model download is acceptable.

`python scripts/verify_release.py` is read-only with respect to native dependencies. The explicit `--bootstrap-native` option is intentionally allowed to clone/build the pinned native dependency as part of the verification gate.

## Release boundary

The repository does **not** claim that a production dataset has been crawled, that a useful model has converged, that external-source training rights have been legally certified, or that target-hardware native inference has passed merely because the source tree is healthy.

Those are runtime and operational facts. The release process requires evidence for them rather than substituting documentation, historical test counts, or placeholder artifacts.
