# Model Lab

Model Lab is the command center and pipeline package for the M²S Model Training Pipeline.

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

The bootstrapper installs framework dependencies and selects the PyTorch channel. CUDA is the default channel; CPU-only hosts can explicitly select `--torch-channel cpu`.

The canonical starter profile is `config/pipeline_config.yaml`. It is bounded and CPU-safe. The larger `config/pipeline_config.full.yaml` profile must be selected explicitly.

After the starter run:

```bash
python3 run_pipeline.py --doctor --hardware-report
python3 run_pipeline.py --list-stages
python3 run_pipeline.py --list-groups
```

Use the PowerShell equivalent on Windows.

## Doctor boundaries

`bootstrap.py --doctor` checks installation and host prerequisites.

`run_pipeline.py --doctor` checks project/runtime readiness.

`--hardware-report` adds conservative host-specific training guidance.

Neither doctor runs pipeline stages.

## Pipeline

The normal pipeline is:

`crawl → clean → dedup → weight → tokenize → shard → train → export`

Stage artifacts are validated using hashes and provenance before resume. Training checkpoints include deterministic state and provenance identities. Export rejects mismatched checkpoint, tokenizer, corpus, shard, source-manifest, or configuration identities.

The starter run is a correctness check, not a useful production training run.

## Desktop and backend

```powershell
python .\launch.py
python .\run_command_center.py --no-browser
```

The desktop launcher starts the existing UI. The UI uses the localhost FastAPI command center and does not implement a second pipeline.

The 1760×990 display value is a desktop verification target, not a universal hardware requirement.

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

## Security

```bash
python -m pip install -r requirements-security.txt
python scripts/security_gate.py
```

The security gate checks tracked source, dependency consistency, and dependency vulnerabilities.

## Native/Termux boundary

The native llama.cpp checkout is bootstrapped separately. GGUF conversion requires `convert_hf_to_gguf.py`; quantized export additionally requires `llama-quantize`.

The historical Android 16/aarch64 quantizer check demonstrates native tool execution on that target. It does not establish that the current source commit has passed the complete native release gate.

## Documentation rule

When this page disagrees with code or workflow configuration, update the page. Do not preserve a stale command merely because it appeared in an older release note.