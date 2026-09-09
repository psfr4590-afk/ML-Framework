# Model Lab

**Model Lab** is the package name for the **M²S Model Training Pipeline** command center.

## Windows launch

```powershell
pip install -r .\requirements.txt
python .\launch.py
```

The launcher starts the existing localhost FastAPI command center when needed and opens the desktop control surface. The UI is designed for a 1760×990 display.

Model Lab navigates the real pipeline and dataset sessions. It does not implement a second copy of the crawler, cleaner, deduplicator, tokenizer, sharder, trainer, or exporter.

## Verify before running expensive work

```powershell
python .\run_pipeline.py --doctor
python .\run_pipeline.py --doctor --hardware-report
```

The doctor is non-destructive. It reports required runtime failures separately from optional capabilities such as CUDA and native llama.cpp tooling. The hardware report shows the conservative training profile Model Lab would select for the current host.

## Bounded smoke run

For a small end-to-end verification experiment:

```powershell
python .\run_pipeline.py --config .\config\pipeline_config.smoke.yaml --no-resume
```

The smoke configuration uses its own dataset-group file containing only the smoke source, so no `--dataset-group` selector is required. It limits source families, crawl depth, page count, vocabulary, sequence length, and training steps. CPU training is explicitly permitted for this validation profile.

## Backend-only mode

```powershell
python .\run_command_center.py --no-browser
```

Without `--no-browser`, the backend opens the localhost command center in the default browser after its health endpoint is ready. The command center binds to localhost by default.

## Production export requirement

Final GGUF export requires a current llama.cpp checkout containing
`convert_hf_to_gguf.py`. Quantized exports also require the built `llama-quantize`
executable. The exporter refuses to claim success when either tool is missing.

## Termux / Android bootstrap

Model Lab supports a headless Termux runtime for the pipeline and native GGUF
export. The Tk desktop UI is intentionally not a dependency of the portable
pipeline test suite.

From the extracted project root:

```bash
python -m pip install -r requirements.txt
bash scripts/bootstrap_llama_cpp.sh
python run_pipeline.py --doctor
python run_pipeline.py --doctor --hardware-report
python -m pytest -q
python scripts/verify_release.py
```

The native bootstrap pins llama.cpp to `b10516` / `b95502b` and uses a reduced
Android-safe build profile. It builds `llama-quantize` and `llama-cli`, which are
the native artifacts required for quantized export and local inference.

If semantic-dedup acceleration is desired and the host supports it:

```bash
python -m pip install -r requirements-optional.txt
```

`sentence-transformers` and FAISS are optional. Without them, Model Lab uses a
deterministic local token-gram fallback so the pipeline remains operational.

`python scripts/verify_release.py` is intentionally read-only. To explicitly
clone/build the native dependency as part of verification, use:

```bash
python scripts/verify_release.py --bootstrap-native
```
