# ML-Framework

**ML-Framework** is the public source repository for **Model Lab**, the **M²S Model Training Pipeline**: an end-to-end, local-first system for building training datasets, training a model, and exporting it for local inference.

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
- hardware/CUDA readiness checks and conservative hardware-aware training profiles
- local training and checkpoint management
- GGUF export for local inference
- a localhost FastAPI command center and desktop control surface
- contract, regression, structure, and machine-environment tests
- release verification tooling

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
- [Dataset Provenance and Source Policy](docs/development/DATA_PROVENANCE.md)
- [Project State](docs/development/PROJECT_STATE.md)
- [Source of Truth](docs/development/SYNC_SOURCE_OF_TRUTH.md)
- [Release Checklist](docs/release/RELEASE_CHECKLIST.md)
- [Release Readiness](docs/release/RELEASE_READINESS_PLAN.md)
- [Release Verification](docs/release/RELEASE_VERIFICATION_REPORT.md)
- [Build Manifest](docs/release/BUILD_MANIFEST.json)
- [Audit Report](docs/verification/AUDIT_REPORT.md)
- [Verification](docs/verification/VERIFICATION.md)
- [Verification Checklist](docs/verification/VERIFICATION_CHECKLIST.md)

## Seeded dataset groups

Ten dataset groups are preconfigured:

- `swe_cs_systems` — software engineering, computer science, and systems
- `ai_ml_cybersec_dataeng` — AI/ML, cybersecurity, and data engineering
- `sci_reasoning_forensics_formal` — scientific reasoning, forensics, and formal methods
- `domain_finance_bio_robotics` — finance, biology, robotics, and related domains

General web seeds live in `config/seed_urls.txt`.

## Quick start

There is exactly one canonical first-run path. From the project root, install with the bootstrapper, verify the environment, then run the default starter profile. Do not make a first-run decision about profiles or training scale. Humanity has suffered enough configuration menus.

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

Each stage reads a verified artifact from the previous stage and writes a new artifact with a manifest containing provenance and hashes. If an existing artifact does not match the expected provenance or integrity data, it is rebuilt instead of being silently reused. This prevents an old or differently prepared dataset from leaking into tokenization, sharding, or training.

Training checkpoints persist the model, optimizer, scaler, global RNG state, train/validation shard order, shard cursor, and loader RNG state. Resume therefore continues from the same data position instead of merely restoring the model weights and accidentally replaying a different token sequence. Checkpoints without the required deterministic state or matching provenance are rejected rather than silently resumed.

Final export is stricter still. The checkpoint must carry the canonical pipeline configuration identity, training/model configuration identities, seed, and shard-manifest identity. The current tokenizer, weighted-corpus manifest, and shard manifest must belong to the same pipeline configuration. A mismatch stops export before an artifact can be presented as a valid model.

The starter profile uses a small real crawl and only two training steps. It is a correctness check, not a useful model-training run. For serious training, inspect the hardware report first and then explicitly choose an appropriate larger configuration.

## Windows launch

After the first-run path is healthy:

```powershell
python .\launch.py
```

`launch.py` is the desktop entry point. It starts the existing desktop control surface, which uses the localhost FastAPI command center as its backend. The UI is designed for a 1760×990 display.

Model Lab navigates the real pipeline and dataset sessions. It does not implement a second copy of the crawler, cleaner, deduplicator, tokenizer, sharder, trainer, or exporter.

## Backend-only mode

```powershell
python .\run_command_center.py --no-browser
```

Without `--no-browser`, the backend opens the localhost command center in the default browser after its health endpoint is ready. The command center binds to localhost by default.

## Production verification

The standard release check is:

```bash
python scripts/verify_release.py
```

This runs compilation, the full test suite, and the required project/runtime doctor. It does not claim that machine-specific native export prerequisites were checked. Use `--bootstrap-native` when the release check must also clone/build and verify the supported llama.cpp toolchain.

Security/release dependency auditing is explicit:

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
```

The security gate checks tracked source for common secret patterns, verifies installed dependency consistency with `pip check`, and runs `pip-audit`. It is a gate, not a decorative report. A missing audit tool or failing audit is a failure.

GitHub Actions runs the same security gate on pushes and pull requests and provides a separate production release workflow for native export verification. The CI path also runs the bootstrap doctor on a clean checkout, so the canonical onboarding path is exercised rather than merely documented.

## Production export requirement

Final GGUF export requires a current llama.cpp checkout containing
`convert_hf_to_gguf.py`. Quantized exports also require the built `llama-quantize`
executable. The exporter refuses to claim success when either tool is missing or when the training provenance chain is incomplete or inconsistent.

## Termux / Android native toolchain

Model Lab supports a headless Termux runtime for the pipeline and native GGUF
export. The Tk desktop UI is intentionally not a dependency of the portable
pipeline test suite.

To prepare the native llama.cpp toolchain after the first-run validation:

```bash
bash scripts/bootstrap_llama_cpp.sh
python scripts/verify_release.py --bootstrap-native
```

The native bootstrap uses a reduced Android-safe build profile when running under
Termux and builds `llama-quantize`, the native artifact required for quantized
export. The Python-side GGUF converter remains part of the pinned llama.cpp
checkout. The desktop/native verification path can additionally build and verify
`llama-cli` where that target is supported.

`sentence-transformers` and `faiss-cpu` are required runtime dependencies because semantic deduplication is a required pipeline capability. They are installed by both the package metadata and the canonical requirements file. The configured embedding model is still kept local by default; set `allow_model_download: true` only when an explicit model download is acceptable.

`python scripts/verify_release.py` is read-only with respect to native dependencies. The explicit `--bootstrap-native` option is the exception: it is intentionally allowed to clone/build the pinned native dependency as part of the verification gate.
