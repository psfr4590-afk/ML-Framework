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

The repository has one canonical first-run path. Start from the project root and use the bootstrapper for installation and environment checks:

### Windows PowerShell

```powershell
python .\bootstrap.py --install
python .\bootstrap.py --doctor
python .\run_pipeline.py --config .\config\pipeline_config.smoke.yaml --no-resume
```

### Linux / macOS / Termux

```bash
python3 bootstrap.py --install
python3 bootstrap.py --doctor
python3 run_pipeline.py --config config/pipeline_config.smoke.yaml --no-resume
```

The smoke run is the recommended first useful run. It is bounded, CPU-safe, and designed to prove that the pipeline can produce and chain real artifacts without committing a newcomer to a long training job.

After the smoke run succeeds, inspect the host before doing expensive work:

```powershell
python .\run_pipeline.py --doctor --hardware-report
```

or:

```bash
python3 run_pipeline.py --doctor --hardware-report
```

On Windows, `python .\launch.py` starts the localhost command center and desktop control surface after the environment is ready. Headless users can use `python run_command_center.py --no-browser` instead.

For a non-destructive release check:

```powershell
python .\scripts\verify_release.py
```

The release verifier explicitly distinguishes automated checks from target-machine checks. A skipped hardware check is not reported as a fake pass.

## Hardware-aware training

Training can use an explicit preset, or Model Lab can choose a conservative profile based on the detected hardware. Auto-sizing changes the model preset, sequence length, microbatch geometry, evaluation budget, checkpoint cadence, and total step budget together rather than relying on a parameter-only memory estimate.

Enable it in `config/pipeline_config.yaml`:

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

## Bounded smoke test

`config/pipeline_config.smoke.yaml` is the canonical newcomer validation profile. It uses a dedicated dataset-group file, bounded source limits, a small vocabulary and sequence length, and a tiny training budget with CPU training explicitly permitted.

The smoke profile is a real pipeline run, not merely a unit-test shortcut. It is intended to answer one question quickly: **can this checkout build a useful chain of artifacts on this machine?**

## Command center

The FastAPI command center is localhost-only by default. It exposes dataset lifecycle, ingestion, stage control, credential management, crawler telemetry, and system information through the `/api/*` surface. The desktop launcher can start the backend and UI together; `run_command_center.py --no-browser` starts the backend without opening a browser.

## Security and generated data

Credentials belong in the runtime credential store or environment variables, never in Git. Dataset outputs, checkpoints, caches, scratch data, logs, and native build products are runtime artifacts and are intentionally excluded from the public source tree.

The crawler is bounded and security-conscious: it applies URL validation, request timeouts, retries, politeness delays, robots handling where configured, content-size limits, and local/private-network refusal rules.

## Verification boundary

Automated CI covers Python compilation and the repository test suite. Environment-dependent gates remain explicit: CUDA availability, native llama.cpp binaries, network access, and human-visible Windows/Tkinter acceptance depend on the target machine. This distinction is intentional.

## License

See `LICENSE` for the project license.
