# ML-Framework Verification and Test Plan

**Document ID:** MLF-GOV-005  
**Version:** 1.0.0  
**Status:** Approved verification baseline  
**Prepared:** 2026-10-11  
**Approval:** Approved by product owner on 2026-10-11

## 1. Purpose

This plan defines how requirements are verified. A passing subset of tests does not establish release readiness. Every result must be tied to the source revision and relevant environment; skipped, blocked, or absent evidence remains unverified.

## 2. Verification levels

1. **Static checks:** formatting, linting, type checks, dependency/security scans, secret/path checks, and repository contracts where configured.
2. **Unit tests:** isolated logic, validation, state transitions, metrics, path handling, and serialization behavior.
3. **Component/contract tests:** API, database, orchestrator, stage-worker, manifest, and external-tool boundaries.
4. **Integration tests:** multi-stage workflow, persistence, restart/recovery, and provenance chain.
5. **End-to-end tests:** browser Command Center actions through backend execution and persisted status/results.
6. **Environment acceptance:** clean clone/install/startup on each claimed supported environment, including ZIP/source-download paths if supported.
7. **Runtime/export acceptance:** real native bootstrap and inference, supported export validation, and target-runtime inference where claimed.
8. **Release certification:** a fixed candidate with complete mandatory evidence, security results, artifact identity, traceability, and known-limitations record.

## 3. Required test dimensions

For each mandatory requirement, cover normal behavior, invalid inputs, boundary cases, failure behavior, and recovery where applicable. Include subprocess nonzero exits, cancellation, timeout, missing dependencies, interrupted writes, malformed manifests, mismatched hashes, missing artifacts, and stale UI state where relevant.

Security testing must include path traversal and destructive-path controls, sensitive-value redaction, untrusted artifact handling, dependency integrity, and disclosed external transfers. Persistence testing must inject write failures and confirm that partial state cannot be mistaken for valid completed state.

## 4. Command Center vertical slices

At minimum, verify end to end:
- Startup/readiness and capability display.
- Create/configure and launch a supported run.
- Observe status and stage transitions from authoritative backend state.
- Read logs and metrics for the correct run.
- Cancel or fail a run and confirm the terminal state.
- Inspect resulting artifacts and provenance.
- Handle unavailable dependencies and invalid configuration with actionable errors.

A mocked UI test alone does not verify the real browser-to-backend path.

## 5. Clean-environment acceptance

Use a fresh checkout or downloaded source archive in a clean supported environment. Follow only documented steps. Record OS, runtime and dependency versions, hardware where relevant, commands, exit codes, and logs. Confirm no undeclared cache, local file, credential, or previous installation is required. Repeat for every environment explicitly claimed in release materials.

## 6. Native runtime and export acceptance

For a native backend, verify dependency bootstrap, executable provenance, startup, and an actual inference request. For model exports, verify file integrity, metadata/provenance pairing, format-specific validation, and actual loading/inference in the named target runtime when that compatibility is claimed. A successful build or file-existence check is insufficient.

## 7. Training and quality evidence

Record exact data/tokenizer/shard identity, configuration, software/backend versions, checkpoints, metrics, and evaluation method. A short smoke run proves only that the tested path executed. Claims of convergence or model quality require a predeclared evaluation method, sufficient training/evaluation evidence, and explicit limitations.

## 8. Evidence record

Each verification record should include requirement IDs, tested revision, environment, command/procedure, expected result, actual result, status (`PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, or `NOT RUN`), logs/artifacts, and reviewer/date where required. Preserve failure evidence. Do not aggregate away a failed mandatory gate.

## 9. Release gate

Release certification requires all mandatory checks in the approved release profile to pass, clean-environment and core end-to-end workflows to pass, supported exports to validate, and no unresolved hard blocker. Any mandatory failed, blocked, or untested gate means NO-GO. CI green is necessary evidence but is not sufficient release certification.

## 10. Baseline authority

This plan was approved by the product owner on 2026-10-11. Updates must identify impacted requirements and preserve the distinction between automated test success and demonstrated release capability.