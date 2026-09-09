# Model Lab Release-Readiness Plan

This document outlines the prioritized work required to bring ML-Framework to production-ready status. The plan is organized by priority level with clear acceptance criteria for each item.

---

## P0: Critical Security & Functionality (Blocking Release)

These items must be completed before any production release. They address fundamental correctness, security, and end-to-end pipeline integrity.

### P0.1: Fix ShardDataLoader SHA verification

**Problem:** The `ShardDataLoader` class verifies manifest entry sizes against on-disk file sizes, but does not verify the SHA256 hash of each shard file. This creates a gap where corrupted shard data could go undetected during training.

**Current state:** 
- File: `pipeline/shardwriter/shard_writer.py` (lines 212–245)
- `__init__` validates manifest presence and file sizes
- SHA256 hashes are written to the manifest (line 149)
- Hashes are NOT verified on load

**Acceptance Criteria:**
- [ ] `ShardDataLoader.__init__` computes SHA256 for each shard file on load
- [ ] Computed hash is compared against the manifest entry
- [ ] Mismatch raises `RuntimeError` with clear provenance message
- [ ] Performance is acceptable for large shard directories (>100GB)
- [ ] Test case: corrupt a shard file and verify detection on load

**Related:** `pipeline/integrity.py` already has `sha256_file()` utility.

---

### P0.2: Harden SSRF/DNS-rebinding behavior

**Problem:** The command center and crawler have network boundary assumptions that are not explicitly enforced. The crawler accepts URLs without explicit restrictions on local/private address ranges, which could be exploited via DNS rebinding or misconfigured redirects.

**Current state:**
- File: `pipeline/crawler/` (not yet audited)
- File: `command_center/` listens on `127.0.0.1:8000` by default
- No documented SSRF/DNS-rebinding mitigations

**Acceptance Criteria:**
- [ ] Crawler URL validation explicitly rejects private IP ranges (RFC 1918, link-local, loopback)
- [ ] DNS rebinding resistance: crawler validates the original hostname after resolution
- [ ] Redirects are followed with the same origin restrictions
- [ ] Command center explicitly binds to loopback only (no network mode)
- [ ] Security boundary documented in `SECURITY.md`
- [ ] Unit test: attempted SSRF payloads are rejected

**Related:** See `SECURITY.md` for current policy.

---

### P0.3: Lock down command-center remote exposure

**Problem:** The command center API endpoints expose dataset lifecycle, stage control, and credential management. These must never be accessible beyond localhost, even if a user misconfigures the binding or proxy.

**Current state:**
- File: `run_command_center.py` binds to `127.0.0.1:8000`
- File: `command_center/web.py` routes `/api/*` endpoints with no auth layer
- No explicit CORS or remote-access rejection headers

**Acceptance Criteria:**
- [ ] Command center middleware explicitly rejects requests not from `127.0.0.1` or `::1`
- [ ] Clear error message for remote attempts (not silent 403)
- [ ] Middleware is applied to all routes in `command_center/web.py`
- [ ] Documentation: clearly state that the command center is never meant for remote access
- [ ] Test case: attempt requests from `0.0.0.0` or external IP, expect rejection

---

### P0.4: Add real end-to-end starter pipeline test

**Problem:** The test suite does not include an actual end-to-end run of the full pipeline using the smoke-test configuration. This means we cannot verify that the entire artifact chain works in CI.

**Current state:**
- File: `tests/` contains unit and module-level tests
- File: `config/pipeline_config.smoke.yaml` exists but is not tested
- No test exercises: `crawl → clean → dedup → weight → tokenize → shard → train → export`

**Acceptance Criteria:**
- [ ] New test file: `tests/test_e2e_smoke_pipeline.py`
- [ ] Test runs `run_pipeline.py --config config/pipeline_config.smoke.yaml --no-resume`
- [ ] Verifies that all stages produce expected output files
- [ ] Validates final GGUF export artifact
- [ ] Runs in CI on every commit (may be slow; OK to gate on explicit trigger)
- [ ] Test can be skipped if native llama.cpp toolchain is unavailable

---

### P0.5: Add GGUF round-trip/inference validation

**Problem:** We export to GGUF format but do not verify that the exported model can load and perform inference. Silent export failures or broken models could ship.

**Current state:**
- File: `pipeline/exporter/` handles HF → GGUF conversion
- File: `scripts/verify_release.py` does not validate GGUF inference
- No test calls `llama.cpp` to actually load and run the exported model

**Acceptance Criteria:**
- [ ] After GGUF export, attempt to load the model with llama.cpp
- [ ] Generate at least one token from the loaded model
- [ ] Validate generation response is non-empty and not obviously corrupted
- [ ] Export manifest includes inference validation results
- [ ] Test file: `tests/test_gguf_inference.py`
- [ ] Test can be skipped if `llama-cli` is not available

---

## P1: Pipeline Robustness & Correctness

These items improve reliability, error recovery, and determinism. They are important for production use but not blocking an initial release if P0 items are complete.

### P1.1: Run Python test suite on Windows CI

**Problem:** The pipeline supports Windows (PowerShell, Tk UI, native builds), but automated tests do not run on Windows. Subtle Windows-specific bugs could escape.

**Current state:**
- File: `.github/workflows/` may not have Windows test job
- Tests pass on Linux; Windows behavior is untested in CI

**Acceptance Criteria:**
- [ ] Add GitHub Actions job for Windows (Python 3.11, latest)
- [ ] Job runs `python -m pytest -q` on Windows
- [ ] All tests pass on Windows or are marked `@pytest.mark.skip(platform="windows")`
- [ ] Workflow file documents the Windows test scope

---

### P1.2: Build failure-path tests around every pipeline stage

**Problem:** When a pipeline stage fails (e.g., network error during crawl, OOM during training), we have limited test coverage for recovery and error reporting.

**Current state:**
- File: `tests/` covers happy path
- No tests for: crawler timeout, missing credentials, shard corruption mid-training, etc.

**Acceptance Criteria:**
- [ ] For each stage in `STAGES`, create at least one failure scenario test
- [ ] Test verifies: stage reports error, dataset state is consistent, retry is possible
- [ ] Examples: network error in crawl, invalid tokenizer path, training OOM
- [ ] File: `tests/test_stage_failures.py`

---

### P1.3: Make checkpoint resume semantics explicitly deterministic or explicitly non-deterministic

**Problem:** The trainer can resume from a checkpoint, but it is unclear whether the resumed run will produce bit-identical results. This ambiguity makes reproducibility guarantees unclear.

**Current state:**
- File: `pipeline/trainer/train.py` handles checkpoint save/load
- Resume uses the same RNG seed, optimizer state, but training may not be deterministic
- Documentation does not clearly state the contract

**Acceptance Criteria:**
- [ ] **Option A (Deterministic):** Verify that resuming from a checkpoint produces the same loss curve and model weights
  - Requires: deterministic RNG, CUDA determinism settings, etc.
  - Document: `pipeline/trainer/README.md`
- [ ] **Option B (Non-deterministic, but repeatable):** Document that resume is NOT guaranteed bit-identical
  - Provide a way to mark a checkpoint as "diverged" if resumed
  - Recommend: full re-training from scratch for production
- [ ] Checkpoint manifest includes the contract
- [ ] Test: `tests/test_checkpoint_semantics.py`

---

### P1.4: Make artifact/stage dependency resolution explicit rather than opportunistic

**Problem:** The orchestrator checks for shard files, checkpoint files, etc., but the dependency resolution logic is implicit. Changing output paths or naming conventions silently breaks recovery.

**Current state:**
- File: `pipeline/orchestrator.py` checks for stage output using glob patterns
- File: `command_center/store.py` has hardcoded stage checks (line 145+)
- If a stage produces no output or unexpected filename, resume may silently skip it

**Acceptance Criteria:**
- [ ] Each stage produces an explicit **stage contract** file (e.g., `stage_complete.manifest.json`)
- [ ] Manifest documents: output files, checksums, version, schema
- [ ] Orchestrator reads manifests instead of globbing
- [ ] If manifest is missing or invalid, stage is marked "incomplete" (not reused)
- [ ] File: `pipeline/contracts/stage_manifest.py` defines schema
- [ ] Test: missing/corrupt manifest is detected before reuse

---

### P1.5: Unify export checkpoint validation with training checkpoint validation

**Problem:** Training checkpoints and export checkpoints (HF models) are validated separately with different logic. This duplication could lead to inconsistency.

**Current state:**
- File: `pipeline/trainer/train.py` validates training checkpoints
- File: `pipeline/exporter/` validates HF checkpoints before GGUF conversion
- No shared validation logic

**Acceptance Criteria:**
- [ ] Create `pipeline/integrity.py` function: `validate_checkpoint(path, expected_config)`
- [ ] Function checks: file exists, SHA256 matches, config matches, model is loadable
- [ ] Training and export both use this function
- [ ] Test coverage for: missing file, wrong config, corrupted weights

---

## P2: Architecture & Documentation (Nice to Have)

These items improve code quality, maintainability, and operational clarity. They are lower priority for the release but recommended for long-term production use.

### P2.1: Break orchestrator into stage components

**Problem:** `pipeline/orchestrator.py` is monolithic and handles stage sequencing, recovery, artifact chaining, and logging. It is hard to test and hard to extend.

**Current state:**
- File: `pipeline/orchestrator.py` (~500+ lines)
- Single class responsible for many concerns

**Acceptance Criteria:**
- [ ] Refactor into: `StageExecutor`, `ArtifactResolver`, `RecoveryManager`
- [ ] Each component has clear responsibility and testable interface
- [ ] Behavior is identical to original (no functional change)
- [ ] File: `pipeline/orchestrator/` becomes a package

---

### P2.2: Strengthen tokenizer provenance

**Problem:** The tokenizer is trained once and reused. If the tokenizer config or training data changes, we have limited visibility into provenance.

**Current state:**
- File: `pipeline/tokenizer/` trains a tokenizer
- Tokenizer is saved to `output/tokenizer/tokenizer.json`
- No manifest of: training data, config, vocabulary size at training time

**Acceptance Criteria:**
- [ ] Tokenizer save includes manifest: training corpus hash, config, vocab size, special tokens
- [ ] Manifest is validated on load (vocab size must match model config)
- [ ] Documentation: tokenizer is a per-dataset artifact and cannot be reused across datasets

---

### P2.3: Improve credential key management

**Problem:** `command_center/secrets.py` requires `PIPELINE_CREDENTIAL_KEY` environment variable on non-Windows hosts. Key rotation and secure generation are not documented.

**Current state:**
- File: `command_center/secrets.py` uses Fernet encryption
- Key is read from env var
- No guidance on key generation or rotation

**Acceptance Criteria:**
- [ ] Document: "Credential Key Management" in `docs/` or `SECURITY.md`
- [ ] Provide: `scripts/generate_credential_key.py` to create a key
- [ ] Bootstrap process should auto-generate a key if missing (optional)
- [ ] Key rotation strategy documented (if supported)

---

### P2.4: Add concurrency/state-machine tests

**Problem:** The dataset store, credential store, and runner use locks, but concurrency bugs are hard to catch with typical tests.

**Current state:**
- File: `command_center/store.py` uses locking
- File: `command_center/runner.py` uses threading.RLock
- No tests for race conditions or state consistency under concurrency

**Acceptance Criteria:**
- [ ] Test file: `tests/test_concurrency.py`
- [ ] Test multiple threads creating datasets, running stages, updating credentials
- [ ] Verify: no data loss, state machine never enters invalid state
- [ ] Use `pytest-timeout` to catch deadlocks

---

### P2.5: Clean up release documentation so "verified" and "tested" aren't treated as interchangeable

**Problem:** The release checklist and verification reports use terms like "verified," "tested," "checked," and "validated" inconsistently, which clouds the distinction between automated CI checks and manual/environment-dependent verification.

**Current state:**
- File: `RELEASE_CHECKLIST.md` mixes automated and manual gates
- File: `RELEASE_VERIFICATION_REPORT.md` mixes test results and environment checks

**Acceptance Criteria:**
- [ ] Define clear terminology:
  - **"Compiled"**: Python source passed through `python -m compileall`
  - **"Tested"**: Ran automated unit/integration tests in CI
  - **"Verified"**: Ran manual or environment-specific checks
  - **"Validated"**: End result was manually inspected by a human
- [ ] Rewrite `RELEASE_CHECKLIST.md` using consistent terminology
- [ ] Rewrite `RELEASE_VERIFICATION_REPORT.md` with clear separation
- [ ] Update `scripts/verify_release.py` to report using this taxonomy

---

## Tracking & Automation

- Each P0 item **must** have a corresponding GitHub Issue with acceptance criteria as checkboxes
- P1 and P2 items should have issues for visibility but are not blocking
- CI workflow should fail if any P0 acceptance criterion is not met
- Release cut (Git tag) should be blocked until all P0 issues are closed

---

## Summary Table

| Priority | Item | Owner | Target Date | Status |
|----------|------|-------|-------------|--------|
| P0 | ShardDataLoader SHA verification | — | — | — |
| P0 | Harden SSRF/DNS-rebinding behavior | — | — | — |
| P0 | Lock down command-center remote exposure | — | — | — |
| P0 | Add real end-to-end starter pipeline test | — | — | — |
| P0 | Add GGUF round-trip/inference validation | — | — | — |
| P1 | Run Python test suite on Windows CI | — | — | — |
| P1 | Build failure-path tests around every pipeline stage | — | — | — |
| P1 | Make checkpoint resume semantics explicit | — | — | — |
| P1 | Make artifact/stage dependency resolution explicit | — | — | — |
| P1 | Unify export checkpoint validation | — | — | — |
| P2 | Break orchestrator into stage components | — | — | — |
| P2 | Strengthen tokenizer provenance | — | — | — |
| P2 | Improve credential key management | — | — | — |
| P2 | Add concurrency/state-machine tests | — | — | — |
| P2 | Clean up release documentation terminology | — | — | — |

