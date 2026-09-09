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

## Seeded dataset groups

Four dataset groups are preconfigured:

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

The bootstrapper installs framework dependencies first, then installs PyTorch from the official CPU wheel index by default. This keeps the canonical first run from silently pulling a large host-specific CUDA bundle onto a low-resource machine. Hosts that intentionally want the default PyPI PyTorch wheel can use `python bootstrap.py --install --torch-channel default`.

After the starter run succeeds, inspect the host before doing expensive work:

```powershell
python .\run_pipeline.py --doctor --hardware-report
```

or:

```bash
python3 run_pipeline.py --doctor --hardware-report
```

On Windows, `python .\launch.py` starts the localhost command center and desktop control surface after the environment is ready. The desktop target window is **1760x990**, with a usable minimum of 1280x720. Headless users can use `python run_command_center.py --no-browser` instead.

For a non-destructive release check:

```powershell
python .\scripts\verify_release.py
```

The release verifier explicitly distinguishes automated checks from target-machine checks. A skipped hardware check is not reported as a fake pass.

## Installation and packaging roles

The bootstrapper is the canonical full-runtime installer. It deliberately owns PyTorch installation so the project can choose a CPU wheel by default and avoid imposing a host-specific CUDA build on every user.

The repository also contains standard Python package metadata in `pyproject.toml`. This supports packaging and installation tooling for the Python modules. The package metadata intentionally does not declare PyTorch, because PyTorch is installed separately by the bootstrapper. If you install the package directly with `pip install .`, install the host-appropriate PyTorch requirement separately, or use `bootstrap.py --install` for the supported end-to-end setup.

The `mlab` console command is the packaged equivalent of the pipeline CLI:

```bash
mlab --help
```

For a first run, prefer `run_pipeline.py` through the canonical bootstrap workflow above so repository-local configuration and artifacts remain explicit.

## Hardware-aware training

Training can use an explicit preset, or Model Lab can choose a conservative profile based on the detected hardware. Auto-sizing changes the model preset, sequence length, microbatch geometry, evaluation budget, checkpoint cadence, and total step budget together rather than relying on a parameter-only memory estimate.

Enable it in `config/pipeline_config.full.yaml` for a larger run, or keep the starter defaults for the first run:

```yaml
train:
  auto_size: true
  model_preset: "85M"   # fallback/manual value when auto_size is false
  allow_cpu_training: false
```

For a prepared shard set, inspect the recommendation before starting a long run:

```powershell
python .\scripts\recommend_model.py --shard-dir .\output\shards
```

The recommender reports the hardware tier and selected profile. It does not invent a wall-clock estimate unless observed throughput is supplied.

## Bounded verification profile

`config/pipeline_config.smoke.yaml` is retained as a dedicated maintainer/verification profile. It is intentionally separate from the canonical starter profile so documentation, tests, and newcomer instructions do not have two competing definitions of "first run".

The verification profile is also a real, bounded pipeline run. It is useful for validating the end-to-end artifact chain in automation or when explicitly testing the smoke configuration, but it is not required for normal first-run use.

## Command center

The FastAPI command center is localhost-only by default. It exposes dataset lifecycle, ingestion, stage control, credential management, crawler telemetry, and system information through the `/api/*` surface. The desktop launcher can start the backend and UI together; `run_command_center.py --no-browser` starts the backend without opening a browser.

## Security and generated data

Credentials belong in the runtime credential store or environment variables, never in Git. Dataset outputs, checkpoints, caches, scratch data, logs, and native build products are runtime artifacts and are intentionally excluded from the public source tree.

The crawler is bounded and security-conscious: it applies URL validation, request timeouts, retries, politeness delays, robots handling where configured, content-size limits, and local/private-network refusal rules.

## Verification boundary

Automated CI covers Python compilation and the repository test suite. Environment-dependent gates remain explicit: CUDA availability, native llama.cpp binaries, network access, and human-visible Windows/Tkinter acceptance depend on the target machine. The documented desktop target is 1760x990 with a usable minimum of 1280x720. This distinction is intentional.

## License

See `LICENSE` for the project license.
