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

`bootstrap.py --install` installs the framework dependencies first, then installs PyTorch from the official CUDA wheel index by default. CPU-only hosts can explicitly use `--torch-channel cpu`, while `--torch-channel default` uses the standard PyPI PyTorch channel.

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

## Clone-and-run path

The final deployment phase exposes one stable command surface:

```text
mlframework doctor
mlframework smoke
mlframework dataset
mlframework train
mlframework evaluate
mlframework export
mlframework infer
mlframework status
mlframework runs
```

From a fresh clone:

```bash
git clone https://github.com/psfr4590-afk/ML-Framework.git
cd ML-Framework
python3 bootstrap.py --install
python3 -m pip install -e .
mlframework doctor
mlframework smoke
```

On Windows PowerShell, use `python` instead of `python3`. Bootstrap now auto-selects the CPU or CUDA PyTorch wheel from detected NVIDIA hardware unless an explicit `--torch-channel` override is supplied.

The CLI resolves all repository paths from its installed entry point. It does not require a developer-specific absolute path or manual YAML edits for the starter workflow.

```text
doctor → smoke → dataset → train → evaluate → export → infer
```

The doctor is a preflight, not a claim that generated datasets or checkpoints already exist. Its Dataset and Tokenizer checks validate that the clean-clone contracts are present. llama.cpp is allowed to be a warning before native export; `mlframework export` bootstraps the pinned native dependency.

## What happens during a run

The normal pipeline is intentionally linear:

`crawl → clean → dedup → weight → tokenize → shard → train → export`

Each stage reads a verified artifact from the previous stage and writes a new artifact with a manifest containing provenance and hashes. If an existing artifact does not match the expected provenance or integrity data, it is rebuilt instead of being silently reused. This prevents an old or differently prepared dataset from leaking into tokenization, sharding, or training.

Training checkpoints persist the model, optimizer, scaler, global RNG state, train/validation shard order, shard cursor, and loader RNG state. Resume therefore continues from the same data position instead of merely restoring the model weights and accidentally replaying a different token sequence. Checkpoints without the required deterministic state or matching provenance are rejected rather than silently resumed.

Final export is stricter still. The checkpoint carries independent dataset, tokenizer, shard, training, model, and source-definition identities, plus explicit upstream artifact relationships. The current tokenizer, weighted-corpus manifest, and shard manifest must be compatible with those identities. A mismatch stops export before an artifact can be presented as a valid model. Historical checkpoints using the former pipeline-wide identity are preserved as legacy evidence rather than rewritten.

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
Termux and builds only `llama-quantize`, the native artifact required for
quantized export. The Termux build is serialized to reduce memory pressure during
compilation. The Python-side GGUF converter remains part of the pinned llama.cpp
checkout. The desktop/native verification path can additionally build and verify
`llama-cli` where that target is supported.

On 2026-09-29, the Termux path was independently exercised on Android 16/aarch64:
the pinned checkout reached the `llama-quantize` target, produced an Android ELF
executable at `third_party/llama.cpp/build-model-lab/bin/llama-quantize`, and the
binary successfully executed its help command. This is native-tool evidence, not
a claim that the complete Python release gate has passed on Termux.

`sentence-transformers` and `faiss-cpu` are required runtime dependencies for semantic deduplication and are installed by the canonical bootstrap path. The default embedding model remains local-only; set `allow_model_download: true` explicitly if the model may be downloaded.

`python scripts/verify_release.py` is read-only with respect to native dependencies. The explicit `--bootstrap-native` option is the exception: it is intentionally allowed to clone/build the pinned native dependency as part of the verification gate.


## Final RC release gate

The ten implementation phases are complete only when the final RC gate is green. Run:

```bash
python scripts/verify_release.py --bootstrap-native --ui-probe --clean-clone
```

The gate writes one machine-readable report to `release-evidence/release_report.json`. It records the status of tests, configuration, provenance, lineage, dataset and source retrieval, checkpoint and best checkpoint, reproducibility, hardware, auto-sizing, ETA, evaluation, SQLite persistence, UI/backend connectivity, GGUF export and native inference, clean-clone acceptance, documentation, secrets, Git state, and release artifacts.

`UNKNOWN` is never promoted to `PASS`. The full RC invocation requires the UI probe and clean-clone acceptance path, so missing evidence fails the release gate rather than being quietly omitted.

The report is the authoritative release evidence summary. Human-readable console output remains useful for diagnosis, but release automation should consume the JSON report and its top-level `status`.
