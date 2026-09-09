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
```

The doctor is non-destructive. It reports missing Python packages, CUDA availability,
and llama.cpp export tooling before a crawl or training run starts.

## Backend-only mode

```powershell
python .\run_command_center.py --no-browser
```

The command center binds to localhost by default.

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
