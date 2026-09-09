# Model Lab

**Model Lab** is the package name for the **M²S Model Training Pipeline** command center.

## First run

There is exactly one canonical first-run path. From the extracted project root, install with the bootstrapper, run the non-destructive doctor, then run the default starter profile.

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

The default `config/pipeline_config.yaml` is the canonical starter profile. It is deliberately bounded and CPU-safe, and it exercises the real pipeline and artifact chain without starting a long production training job. A newcomer does not need to choose a profile for the first run.

If the starter run succeeds, inspect the host before expensive work:

```powershell
python .\run_pipeline.py --doctor --hardware-report
```

or:

```bash
python3 run_pipeline.py --doctor --hardware-report
```

The doctor is non-destructive. It reports required runtime failures separately from optional capabilities such as CUDA and native llama.cpp tooling. The hardware report shows the conservative training profile Model Lab would select for the current host.

## Windows launch

After the first-run path is healthy:

```powershell
python .\launch.py
```

The launcher starts the existing localhost FastAPI command center when needed and opens the desktop control surface. The UI is designed for a 1760×990 display.

Model Lab navigates the real pipeline and dataset sessions. It does not implement a second copy of the crawler, cleaner, deduplicator, tokenizer, sharder, trainer, or exporter.

## Backend-only mode

```powershell
python .\run_command_center.py --no-browser
```

Without `--no-browser`, the backend opens the localhost command center in the default browser after its health endpoint is ready. The command center binds to localhost by default.

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

The native bootstrap pins the supported llama.cpp revisions and uses a reduced
Android-safe build profile. It builds `llama-quantize` and `llama-cli`, which are
the native artifacts required for quantized export and local inference.

If semantic-dedup acceleration is desired and the host supports it:

```bash
python3 -m pip install -r requirements-optional.txt
```

`sentence-transformers` and FAISS are optional. Without them, Model Lab uses a
deterministic local token-gram fallback so the pipeline remains operational.

`python scripts/verify_release.py` is intentionally read-only. To explicitly
clone/build the native dependency as part of verification, use:

```bash
python3 scripts/verify_release.py --bootstrap-native
```
