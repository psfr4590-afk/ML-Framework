# Model Lab

**Model Lab** is the package name for the **M²S Model Training Pipeline** command center.

## First run

There is exactly one canonical first-run path. From the extracted project root, install with the bootstrapper, run the environment preflight, then run the default starter profile.

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

`bootstrap.py --install` installs the framework dependencies first, then installs PyTorch from the official CPU wheel index by default. This keeps the canonical first run from silently pulling a large host-specific CUDA bundle onto a low-resource machine. Hosts that intentionally want the default PyPI PyTorch wheel can use `--torch-channel default`.

The default `config/pipeline_config.yaml` is the canonical starter profile. It is deliberately bounded and CPU-safe, and it exercises the real pipeline and artifact chain without starting a long production training job. A newcomer does not need to choose a profile for the first run.

If the starter run succeeds, inspect the project and host before expensive work:

```powershell
python .\run_pipeline.py --doctor --hardware-report
```

or:

```bash
python3 run_pipeline.py --doctor --hardware-report
```

`bootstrap.py --doctor` and `run_pipeline.py --doctor` have different jobs. The bootstrap doctor checks installation and host prerequisites. The pipeline doctor checks project/runtime readiness. Neither doctor runs pipeline stages. The hardware report adds conservative training guidance for the current host.

Useful read-only inspection commands are also available:

```powershell
python .\run_pipeline.py --list-stages
python .\run_pipeline.py --list-groups
```

or:

```bash
python3 run_pipeline.py --list-stages
python3 run_pipeline.py --list-groups
```

## What happens during a run

The normal pipeline is intentionally linear:

`crawl → clean → dedup → weight → tokenize → shard → train → export`

Each stage reads a verified artifact from the previous stage and writes a new artifact with a manifest containing provenance and hashes. If an existing artifact does not match the expected provenance or integrity data, it is rebuilt instead of being silently reused. This prevents an old or differently prepared dataset from leaking into tokenization, sharding, or training.

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

## Production export requirement

Final GGUF export requires a current llama.cpp checkout containing
`convert_hf_to_gguf.py`. Quantized exports also require the built `llama-quantize`
executable. The exporter refuses to claim success when either tool is missing.

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

If semantic-dedup acceleration is desired and the host supports it:

```bash
python3 -m pip install -r requirements-optional.txt
```

`sentence-transformers` and FAISS are optional. Without them, Model Lab uses a
deterministic local token-gram fallback so the pipeline remains operational.

`python scripts/verify_release.py` is read-only with respect to native dependencies. The explicit `--bootstrap-native` option is the exception: it is intentionally allowed to clone/build the pinned native dependency as part of the verification gate.
