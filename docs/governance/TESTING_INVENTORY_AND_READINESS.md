# Testing Inventory and Readiness Ledger

**Snapshot:** 2026-10-11  
**Repository:** `psfr4590-afk/ML-Framework`  
**Branch under development:** `governance/acceptance-foundation-v1`

This inventory is a discovery baseline, not a test-run report. File presence does not imply that a test currently passes. Runtime status remains **UNKNOWN - NO EXECUTION EVIDENCE** until CI or a reproducible local run provides results.

## Existing test modules discovered on the base branch

### Command Center, runtime, and security
- `tests/test_command_center.py`
- `tests/test_command_center_credentials.py`
- `tests/test_command_center_entrypoint.py`
- `tests/test_command_center_hardening.py`
- `tests/test_command_center_lifespan.py`
- `tests/test_command_center_service.py`
- `tests/test_command_center_stage_sync.py`
- `tests/test_command_center_state.py`
- `tests/test_command_center_vertical_slices.py`
- `tests/test_events.py`
- `tests/test_observability.py`
- `tests/test_production_hardening.py`
- `tests/test_runtime.py`
- `tests/test_security_boundaries.py`

### Artifact integrity, dataset identity, and provenance
- `tests/test_artifact_provenance.py`
- `tests/test_dataset_contract.py`
- `tests/test_dataset_identity.py`
- `tests/test_identity_invalidation.py`
- `tests/test_integrity_regression.py`
- `tests/test_phase1_provenance.py`
- `tests/test_provenance_identity.py`
- `tests/test_retrieval_identity.py`
- `tests/test_shard_integrity.py`
- `tests/test_training_provenance_lineage.py`

### Release, packaging, and environment
- `tests/test_bootstrap.py`
- `tests/test_cli_inspection_contract.py`
- `tests/test_dependency_contract.py`
- `tests/test_doctor.py`
- `tests/test_duplicate_implementation_contract.py`
- `tests/test_entrypoint.py`
- `tests/test_environment_contract.py`
- `tests/test_launcher.py`
- `tests/test_native_toolchain_contract.py`
- `tests/test_package_metadata.py`
- `tests/test_packaging_contract.py`
- `tests/test_release_gate.py`
- `tests/test_release_gate_contract.py`
- `tests/test_release_verification_contract.py`
- `tests/test_release_versioning.py`
- `tests/test_run_pipeline_cli_contract.py`
- `tests/test_stranger_clone_contract.py`
- `tests/test_system_info.py`

### Pipeline, training, evaluation, and ML behavior
- `tests/model_lab/test_machine_environment.py`
- `tests/model_lab/test_model_lab_services.py`
- `tests/model_lab/test_model_lab_structure.py`
- `tests/test_config_validation.py`
- `tests/test_content_parser.py`
- `tests/test_default_config.py`
- `tests/test_experiment_db.py`
- `tests/test_export_cards.py`
- `tests/test_first_run_workflow.py`
- `tests/test_huggingface_crawler.py`
- `tests/test_mlframework_cli.py`
- `tests/test_model_evaluation.py`
- `tests/test_model_sizer.py`
- `tests/test_orchestrator_critical_paths.py`
- `tests/test_orchestrator_streaming.py`
- `tests/test_pipeline_contracts.py`
- `tests/test_phase5_estimation.py`
- `tests/test_phase9_deployment.py`
- `tests/test_run_tracking.py`
- `tests/test_semantic_dedup_global.py`
- `tests/test_semantic_dedup_offline.py`
- `tests/test_semantic_dedup_regression.py`
- `tests/test_tokenizer.py`
- `tests/test_trainer_run.py`
- `tests/test_training_config_contract.py`
- `tests/test_weighter_policy.py`
- `tests/test_weighter_regression.py`

## Governance tests added on the development branch

- `tests/governance/test_requirement_acceptance.py`: 64 exact requirement target names. Assertion quality is mixed; do not treat the 64 names as proof of 64 requirements passing.
- `tests/governance/test_operational_failure_modes.py`: supplemental cancellation, orphan recovery, artifact/provenance, release-gate, and logging-redaction scenarios.

## Critical operational scenarios and evidence status

| Scenario | Intended evidence | Status |
|---|---|---|
| Direct child cancellation | terminate, bounded wait, kill fallback, final state | Implemented; execution unverified |
| Descendant process cleanup | process-group/job-object termination and no surviving descendants | Not implemented/verified |
| Start/cancel race | cancellation during STARTING cannot orphan an untracked process; duplicate launches rejected | Implementation and behavioral tests committed at `32fe5a3` and `624e1e1`; execution unverified |
| Restart recovery | dead PID transitions run/stage to failure; live PID preserved | Test scenarios added; execution unverified |
| PID reuse / stale state | persisted identity cannot mistake unrelated process for worker | Not covered yet |
| Short/encoded secret redaction | raw, JSON-escaped, Base64, URL-encoded forms | Helper and tests added; execution unverified |
| Structured log redaction | nested structured values, exception fields, multiline output | Partial; execution unverified |
| Secrets in traceback/errors | errors from credential retrieval and subprocess setup | Not comprehensively covered |
| Redaction before every sink | file logs, console logs, event payloads, API responses | Not comprehensively audited |
| Artifact tampering | artifact bytes and manifest corruption fail closed | Tests added; execution unverified |
| Provenance mismatch | expected run/config/dataset identity mismatch rejected | Tests added; execution unverified |
| Export validation | incomplete/invalid cards and paired artifacts rejected | Existing `test_export_cards.py`; exact coverage/results unknown |
| Release gate | required flags, no skip-tests, version identity, nonzero exit on failure | Tests added; execution unverified |
| Clean clone | install/test/gate from fresh clone without workspace residue | Existing clean-install CI job; run result not retrieved |
| Whole suite / platform matrix | Linux + Windows, Python 3.11 + 3.14 | CI configured; latest branch result unknown |

## Known limitations to resolve

1. `Popen.terminate()` and `Popen.kill()` only target the direct child. POSIX process groups and Windows Job Objects or equivalent process-tree management are needed for a reliable descendant cleanup guarantee.
2. Startup cancellation intent is now recorded and checked before/after process creation; cancelled state is preserved through final reconciliation. Behavioral tests exist, but need execution. Windows descendant cleanup still needs Job Object containment or an equivalent verified mechanism.
3. Redaction is a best-effort defense. It cannot reliably discover secrets not supplied to the redactor, arbitrary transformations, partial/chunked values, or secrets split across output lines. Prefer structured logging that never logs secret-bearing fields, plus output redaction as defense in depth.
4. Orphan recovery currently relies on PID liveness. PID reuse can preserve a stale run incorrectly; process creation time or a per-run identity should be persisted and validated.
5. No passing execution evidence is claimed by this inventory. Collect CI run URLs, exact commit SHA, platform/Python matrix, pass/fail/skip counts, coverage output, and known pre-existing failures before readiness decisions.


## Evidence ledger update (2026-10-11)

### Acceptance and logging review
- Review document: `docs/governance/ACCEPTANCE_AND_LOGGING_AUDIT.md`.
- Commit: `c2f536f5174cae2831c4c8c8c8233bd458e6234a`.
- Scope: classified behavior-oriented targets versus structural/shallow targets; listed all sink families requiring synthetic-canary tests.
- Result: static review only. Canonical normative catalog could not be retrieved from the repository paths checked; no unsupported requirement interpretations were silently promoted to acceptance criteria.

### CI and regression evidence
- Latest inspected commit: `c2f536f5174cae2831c4c8c8c8233bd458e6234a`.
- GitHub workflow-runs lookup for this SHA: **0 runs returned**.
- Combined commit status lookup: **no status entries returned**.
- Coverage checker: located in the supplied governance package at `v11/check_test_coverage.py` (not at the two repository paths checked). Its CLI requires `--repo-root PATH_TO_ML_FRAMEWORK`; it validates exact test-function presence only, not assertion quality or test execution. Execution remains blocked until a repository checkout is available in the execution environment.
- Baseline SHA / branch SHA test comparison: **NOT RUN**.
- Pytest pass/fail/skip/error counts: **UNKNOWN - NO EXECUTION EVIDENCE**.
- Reason: repository clone/test execution is blocked by network DNS failure in the current environment; GitHub API access does not execute repository code.

### Current decision
No claim of passing tests or CI is made. Before merge, execute the canonical checker and identical pytest commands against base and branch in a network-enabled runner, retain raw logs and exit codes, and classify each delta as pre-existing, regression, setup/environment, or flaky.


## Evidence correction (2026-10-11)

The supplied repository-mapped governance ZIP was inspected after the prior ledger update. It contains the actual coverage checker at `v11/check_test_coverage.py` and the canonical 64-row traceability register in `v11/TRACEABILITY.md`. Therefore, the checker is **located**, not missing; it has not yet been run against the development checkout because this execution environment cannot clone the repository (DNS failure). The checker is deliberately limited to checking required test-function names and must not be treated as proof of behavioral coverage. The newly supplied amendment-candidate ZIP contains 12 governance documents and no checker script; its proposed/effective status must be resolved against the authoritative v1.1.0 package before treating documents as interchangeable. The canonical traceability register states that the reviewed source snapshot was base SHA `f06bbedb55e252cd7033c615733c5d2554a7d0aa`, and marks all requirements `NOT_VERIFIED` pending evidence. No new test counts or pass claims are made.


## Implementation update (2026-10-11)

- Runner start/cancel handling updated on the development branch: commit `32fe5a3dfdc4e24bceb977b86b42820bb1722bb4` records cancellation intent while the runner is in `STARTING`, checks it before process launch and immediately after process registration, and adds a bounded process-tree termination helper for POSIX process groups.
- Cancellation final-state preservation updated at `589c9af872add679751d11af59cb29bdc51bacc8`; terminal reconciliation no longer overwrites a `CANCELLED` stage/status.
- Behavioral regression tests added in `tests/governance/test_runner_lifecycle.py`; latest test commit at time of writing: `433328c51d2010eb9cb4d5f9953098200885f05d`. Tests cover start-window cancellation intent, no subprocess launch after cancellation, terminal-state preservation, and duplicate launch rejection.
- CI/workflow lookup for latest test commit returned zero workflow runs and no commit-status entries. These tests are **not claimed to pass**. Local execution remains blocked by unavailable repository clone/network DNS in this environment.
- Remaining runner risks: Windows process-tree termination is still best-effort and requires Job Object or equivalent descendant containment; concurrent termination ownership should be tested to ensure the stop caller and worker cannot race to terminate the same process group twice.
