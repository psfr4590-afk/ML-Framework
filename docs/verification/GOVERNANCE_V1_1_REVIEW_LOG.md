# Governance v1.1.0 Review Log

**Status:** In progress; review only, not release approval.  
**Purpose:** Preserve investigation results and make each follow-up actionable instead of relying on terminal history.  
**Review worktree examined:** `governance/v1.1.0-import-review` at `79990219e505c4531aa3a61fb9acbeff1cefbc00`.  
**Important baseline note:** The package traceability document identifies source snapshot `f06bbedb55e252cd7033c615733c5d2554a7d0aa`. Findings must be rechecked against the exact candidate commit before being treated as candidate-specific evidence.

## Current disposition

The v1.1.0 package has passed archive/hash integrity checks, package structural validation, and requirement-target existence checks in the review worktree. A selected existing test run passed **88 tests with 1 warning**; a separate governance acceptance suite passed **64 tests**. These are scoped results, not full-suite certification or proof that all requirements are implemented and verified.

All 64 requirements remain `NOT_VERIFIED`. Preserve that status until requirement-specific behavior and candidate-bound evidence justify a change.

## Findings register

| ID | Priority | Status | Finding | Evidence already collected | Next action / exit condition |
|---|---|---|---|---|---|
| GOV-01 | High | Investigating | SQLite schema evolution may not migrate existing databases safely. | Historical schema reports version 1; current code reports version 2, uses `CREATE TABLE IF NOT EXISTS`, then writes the current version to metadata. An explicit migration path was not found in the inspected initializer. | Compare historical/current table and column definitions. If they differ, reproduce upgrade behavior using a disposable legacy database and implement/test an explicit migration. If they match, document that result and add a regression test for version handling. |
| GOV-02 | Medium | Coverage gap | Export-card negative paths lack direct regression coverage in the inspected tests. | Exporter writes dataset and model cards, hashes them, and writes an aggregate manifest; release verifier checks card existence, non-empty content, and hashes. Existing export-card test covers successful creation/lineage. | Add tests for missing, empty, and tampered cards and for export failure/reuse of an existing output directory. Confirm failed exports cannot be mistaken for a completed export. |
| GOV-03 | Low | Coverage gap | ETA/duration disclosure is not consistently verified. | CLI labels duration as estimated and reports it unavailable without observed throughput; Command Center surfaces ETA values. No explicit UI/CLI wording regression test was found in the inspected paths. | Decide required wording in the requirement/acceptance criterion, then add a focused test. Do not change estimator behavior unless a defect is demonstrated. |
| GOV-04 | Medium | Coverage gap | Structured log context is not proven to meet the stated requirement. | Inspected formatters include timestamp, logger/severity, and message; run/stage identifiers exist in tracking/manifest paths, but are not automatically present in every log record. No single test was found proving the required fields together. | Clarify whether structured fields are normative for every event or only relevant events. Add a focused test for required timestamp, severity, run/stage IDs, and event context. |
| GOV-05 | Medium | Test adequacy gap | The doctor non-destructive test does not meaningfully detect filesystem mutation. | Existing test compares paths matching `pipeline/doctor.py` before and after; it does not snapshot datasets, artifacts, file contents, or unexpected files. | Run doctor against a disposable project containing sentinel files and artifacts; compare content hashes and filesystem inventory before/after. |
| GOV-06 | High, cross-cutting | Audit in progress | Some requirement-to-test mappings appear to claim more coverage than their tests establish. | Examples inspected include tests that only check a file exists, README text, or a source-code string for requirements about behavior, security, or data integrity. The structural validator confirms mapping completeness, not semantic adequacy. | Audit mappings in bounded batches. Classify each as behavioral coverage, partial coverage, existence/source smoke check, or missing test. Update only demonstrably inaccurate mappings and keep requirements `NOT_VERIFIED` until evidence exists. |

## Verification evidence and limits

- Package structural validator: passed; 64 unique requirements, 64 complete traceability rows, and 64 unique test IDs.
- Test-target checker: passed; all 64 requirement-specific targets exist. It explicitly does not prove those tests pass or adequately test requirements.
- Selected existing tests: 88 passed, 1 warning. This was a selected test set, not the full repository suite.
- Separate governance acceptance suite: 64 passed, 1 warning.
- Selected-run coverage varied by module; the inspected run reported 44% overall and 6% for `pipeline/orchestrator.py`. These are scoped coverage figures, not full-suite coverage or proof of a product defect.
- No source implementation fix is claimed by this review log.
- No release GO/CERTIFIED decision is made here.

## Working rules for the remainder of the review

1. Every new finding is recorded here before expanding the investigation.
2. A finding must identify its evidence, confidence, and exit condition.
3. Keep confirmed defects separate from test gaps and unverified risks.
4. Prefer one small regression test or one focused implementation change over broad exploratory test runs.
5. Re-run only the relevant tests after a focused change, then run broader gates at the appropriate integration/release checkpoint.
6. Recheck findings against the exact candidate commit and environment before changing any requirement from `NOT_VERIFIED`.
7. Do not merge this review log as evidence that the package or product is certified; it is a tracking artifact only.

## Next checkpoint

Resolve the schema comparison (GOV-01) using a disposable database if needed, then prioritize the traceability audit by hard-gate/security/data-integrity requirements. Add regression tests in separate, focused PRs once each expected behavior is agreed and the relevant failure mode is understood.
