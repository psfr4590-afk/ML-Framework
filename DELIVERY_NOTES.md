# Model Lab 1.3.0 Delivery Notes

This archive is the implemented Model Lab source tree, based on the production-trusted r2 baseline and hardened for the delivery walkthrough.

## Implemented in this delivery

- Global semantic-dedup decision scope across embedding batches. Buffer boundaries no longer create independent duplicate universes.
- Higher-weight semantic duplicates replace lower-weight representatives before final emission.
- Persisted crawler telemetry under each dataset scratch directory (`crawl_stats.json`, `crawl_domains.json`).
- FastAPI endpoints for crawler statistics, domain signal telemetry, and log tail.
- Tk application styling is implemented with a safe fallback for minimal Tk installations.
- `command_center.app` is a real compatibility export of the authoritative FastAPI application rather than a placeholder module.
- Added regression coverage for cross-buffer semantic deduplication.

## Verification performed for this archive

- Python compilation: PASS
- Automated tests: 83 passed, 11 skipped
- FastAPI command-center smoke test: PASS
- Crawler security unit smoke test: PASS for private/local URL classes

## Environment-dependent gates

The source tree contains the complete integration and release gates for tokenizer, CUDA training, llama.cpp conversion, quantization, and runtime inference. This build environment cannot certify those machine-dependent operations because it has no network access for dependency installation, no CUDA runtime, and no native llama.cpp checkout. The release scripts therefore fail closed rather than fabricating a green result.

The intended target-machine sequence remains:

1. install `requirements.txt` with a host-appropriate PyTorch wheel;
2. run `python run_pipeline.py --doctor`;
3. run `python scripts/bootstrap_llama_cpp.sh` (or the Windows PowerShell equivalent);
4. run the complete pytest suite;
5. execute a reduced end-to-end crawl/clean/dedup/weight/tokenize/shard/train/export smoke run;
6. verify GGUF inference with the pinned llama.cpp runtime.

A release is not considered fully runtime-certified until those target-machine gates pass.
