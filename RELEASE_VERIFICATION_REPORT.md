# Release Verification Report

Date: 2026-08-26

## Code-level verification

- Python compilation: PASS
- Automated tests: **82 passed, 11 skipped**
- Checkpoint integrity round-trip: PASS
- Export tensor mapping tests: PASS
- Project-root launch behavior: PASS
- Dataset artifact isolation tests: PASS

## Native/environment verification

The current build environment does **not** contain the required `tokenizers` package or the pinned llama.cpp checkout, and has no CUDA runtime. Therefore the strict release gate correctly remains **BLOCKED** here. This is intentional. The project does not claim a native GGUF conversion it did not execute.

Windows:

```powershell
python -m pip install -r requirements.txt
.\scripts\bootstrap_llama_cpp.ps1
python run_pipeline.py --doctor
python scripts/verify_release.py
```

Termux / Android:

```bash
python -m pip install -r requirements.txt
bash scripts/bootstrap_llama_cpp.sh
python run_pipeline.py --doctor
python scripts/verify_release.py
```

The llama.cpp integration is pinned to upstream release `b10516` / commit `b95502b`. The bootstrap script verifies the resolved Git commit before building.

A final release requires a real reduced end-to-end run through tokenization, sharding, training, GGUF conversion, quantization, and llama.cpp inference.
