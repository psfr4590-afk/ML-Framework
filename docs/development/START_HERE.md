# Model Lab

Model Lab is the command center and pipeline package for the M²S Model Training Pipeline. The repository uses one canonical pipeline implementation and exposes it through the CLI, localhost FastAPI command center, and optional Windows/Tk desktop surface.

## First run

Use the bootstrapper, then the appropriate doctor, then the bounded starter profile.

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

The bootstrapper installs framework dependencies and selects the PyTorch channel. CUDA is the default installation channel; CPU-only hosts can explicitly select `--torch-channel cpu`.

The canonical starter profile is `config/pipeline_config.yaml`. It is bounded and intended for correctness/flow validation rather than useful model pretraining. The larger `config/pipeline_config.full.yaml` profile must be selected explicitly.

## Pipeline

The normal pipeline is:

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

The built-in model is a Llama-style decoder-only transformer with 85M, 117M, and 360M presets. Training uses PyTorch and can select conservative hardware-aware profiles.

Stage artifacts are validated using hashes and provenance before resume. Training checkpoints retain configuration, source/shard identity, seed, optimizer/scaler state, RNG state, and loader state. Export rejects mismatched checkpoint, tokenizer, weighted-corpus, shard, source-manifest, configuration, or vocabulary identities.

Inspect the available stages without running them:

```bash
python3 run_pipeline.py --list-stages
```

Inspect configured dataset groups:

```bash
python3 run_pipeline.py --list-groups
```

A dataset-specific session can be selected with `--dataset-id` after its identity has been validated.

## Doctors and hardware

`bootstrap.py --doctor` checks installation and host prerequisites.

`run_pipeline.py --doctor` checks project/runtime readiness without executing pipeline stages.

`run_pipeline.py --doctor --hardware-report` adds detected hardware and conservative training guidance.

Neither doctor runs pipeline stages.

## Command center

Run the backend directly:

```powershell
python .\run_command_center.py --no-browser
```

Or use:

```bash
python run_pipeline.py --web
```

The FastAPI command center is localhost-only. Mutating API requests require the command-center control header, and dataset ingestion is restricted to the configured imports directory with traversal, absolute-path, and symlink protections.

The command center creates/maintains isolated dataset sessions, launches the canonical pipeline CLI for individual stages, tracks state/events, exposes crawler telemetry, and manages local credentials. It is a control plane, not a second pipeline.

## Desktop

```powershell
python .\launch.py
```

The desktop UI delegates backend actions to the localhost command center. The 1760×990 display value is a UI verification target, not a universal hardware requirement.

## Release verification

Static verification:

```bash
python scripts/verify_release.py
```

Full native verification:

```bash
python scripts/verify_release.py --bootstrap-native
```

The static check covers compilation, Ruff, pytest/coverage, and the required doctor. The native check additionally bootstraps the pinned llama.cpp toolchain and runs the deterministic local release fixture through export and native inference.

The repository enforces **90% aggregate pytest coverage**.

## Security and provenance

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
```

Production datasets require source manifests, source identity, rights/licensing review, and retained artifact lineage. The software provides technical provenance and integrity controls; it does not certify copyright, licensing, consent, or legal compliance.

## Native/Termux boundary

The native llama.cpp checkout is bootstrapped separately under `third_party/llama.cpp/`. GGUF conversion requires `convert_hf_to_gguf.py`; quantized export additionally requires `llama-quantize`. The native release fixture also validates inference through `llama-cli`.

Historical Android 16/aarch64 quantizer evidence demonstrates tool execution on that target. It does not establish that the current source commit has passed the complete native release gate.

## Documentation rule

When this page disagrees with code or workflow configuration, update the page. Do not preserve a stale command merely because it appeared in an older release note.
