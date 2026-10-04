# Model Lab Release Checklist

A release candidate is a source-tree candidate plus reproducible evidence. Production release approval requires every applicable gate below to be backed by current evidence for the exact approved commit.

## 1. Repository and automated gates

- [ ] Exact approved commit is identified and frozen
- [ ] Linux CI passes for that exact commit
- [ ] Windows CI passes for that exact commit
- [ ] Windows PowerShell bootstrap contract passes
- [ ] `python -m compileall -q .` passes
- [ ] `python -m pytest -q` passes with the enforced **90% aggregate coverage threshold**
- [ ] `python run_pipeline.py --doctor` has no required failures
- [ ] Security gate passes: secret scan, `pip check`, and `pip-audit`
- [ ] CodeQL passes for the exact approved commit when configured as a release gate
- [ ] No unintended generated artifacts, credentials, caches, or native build products are tracked

## 2. Native release gate

- [ ] Pinned llama.cpp bootstrap completes at the repository's configured revision
- [ ] `convert_hf_to_gguf.py` exists in the pinned checkout
- [ ] `llama-quantize` exists when quantized export is requested
- [ ] Deterministic network-free release fixture completes
- [ ] Tokenizer and shard contracts pass
- [ ] Reduced training run writes a checkpoint and integrity metadata
- [ ] Checkpoint reload succeeds
- [ ] GGUF F16 export succeeds
- [ ] Requested quantized GGUF export succeeds when requested
- [ ] Export manifest hashes match files on disk
- [ ] Dataset and model cards are generated and hashed
- [ ] `scripts/verify_gguf.py` passes
- [ ] llama.cpp native inference validation passes

## 3. Provenance, security, and reproducibility

- [ ] Every production source has a retained source manifest with identifier, retrieval time, revision, license/usage terms, and raw-source SHA-256 where available
- [ ] Attribution and redistribution requirements are reviewed before publishing a dataset or model
- [ ] Sources without established training rights are excluded
- [ ] Crawler boundary and security tests pass
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

These are not satisfied by the bounded release fixture:

- [ ] Target deployment hardware passes native export/inference
- [ ] Intended production training run completes successfully
- [ ] Training loss/convergence and evaluation evidence are recorded
- [ ] Production dataset provenance/rights review is complete
- [ ] Release artifact is rebuilt from the exact approved source/config/dependency state

Historical reports do not satisfy current gates. Every completed gate should include its execution environment, result, and relevant artifact or log evidence.