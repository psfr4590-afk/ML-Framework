# Model Lab Release Candidate / Production Release Checklist

A release candidate is a source-tree candidate plus reproducible evidence. A production release requires the additional target-environment gates.

## 1. Repository and automated gates

- [x] Current RC source state identified on `main`; release commit must be frozen before tagging
- [x] Linux CI passes on the current `main` source state
- [x] Windows CI passes on the current `main` source state
- [x] Windows PowerShell bootstrap contract passes
- [x] `python -m compileall -q .` passes in CI
- [x] `python -m pytest -q` passes with the declared coverage threshold
- [x] `python run_pipeline.py --doctor` has no required failures
- [x] Security gate passes: secret scan, `pip check`, `pip-audit`
- [x] CodeQL analysis passes on the current `main` source state
- [x] No unintended generated artifacts, credentials, caches, or native build products are tracked

## 2. Native release gate

- [ ] Pinned llama.cpp bootstrap completed and commit is `b95502b...`
- [ ] `convert_hf_to_gguf.py` exists in the pinned checkout
- [ ] `llama-quantize` exists when quantized export is enabled
- [x] Termux/Android native quantizer smoke evidence recorded for 2026-09-29: Android 16/aarch64 executable starts successfully
- [ ] Deterministic network-free release fixture completes
- [ ] Tokenizer and shard contracts pass
- [ ] Reduced training run writes a checkpoint and integrity manifest
- [ ] Checkpoint reload succeeds
- [ ] GGUF F16 export succeeds
- [ ] Requested quantized GGUF export succeeds
- [ ] Export manifest hashes match files on disk
- [ ] Dataset and model cards are generated and hashed
- [ ] `scripts/verify_gguf.py` passes
- [ ] llama.cpp native inference validation passes

## 3. Provenance, security, and reproducibility

- [ ] Every production source has a retained source manifest with identifier, retrieval time, revision, license/usage terms, and raw-source SHA-256 where available
- [ ] Attribution and redistribution requirements have been reviewed before publishing a dataset or model
- [ ] Sources without established training rights are excluded
- [ ] Crawler boundary/security tests pass
- [ ] Untrusted document/archive parsing limits are enforced
- [ ] Credential storage and redaction controls are verified
- [ ] Command-center localhost binding and access controls are verified
- [ ] Dependency vulnerability/license scanning is complete for the release environment
- [ ] Dependency freeze and SBOM are retained

## 4. Artifact lineage

- [ ] Full Git commit SHA is recorded
- [ ] Pipeline configuration SHA-256 is recorded
- [ ] Source manifest SHA-256 is recorded
- [ ] Shard manifest SHA-256 is recorded
- [ ] Model configuration and random seeds are recorded
- [ ] Hardware and driver information are recorded for training runs
- [ ] Deterministic-mode settings are recorded when deterministic output is promised
- [ ] Final GGUF SHA-256 is recorded

## 5. Production-only gates

These are not satisfied by the bounded RC smoke test:

- [ ] Target deployment hardware passes native export/inference
- [ ] Intended production training run completes successfully
- [ ] Training loss/convergence and evaluation evidence are recorded
- [ ] Production dataset provenance/rights review is complete
- [ ] Release artifact is rebuilt from the exact approved source/config/dependency state

Every completed gate should include its execution environment, result, and relevant artifact or log evidence. Historical reports do not satisfy current gates.
