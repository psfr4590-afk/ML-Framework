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
| GOV-01 | Low | Reduced risk; no defect demonstrated | Schema-version handling has no explicit migration/version compatibility guard in the inspected initializer. | Historical schema v1 and current schema v2 have identical table and column definitions in an in-memory SQLite comparison. The initializer runs `CREATE TABLE IF NOT EXISTS` then unconditionally writes the current schema version. No existing-database upgrade failure was reproduced. | Do not build a migration framework without evidence of a schema change. Add a focused test for legacy schema metadata/version handling if warranted; revisit if a future schema changes tables or columns. |
| GOV-02 | Medium | Coverage gap | Export-card negative paths lack direct regression coverage in the inspected tests. | Exporter writes dataset and model cards, hashes them, and writes an aggregate manifest; release verifier checks card existence, non-empty content, and hashes. Existing export-card test covers successful creation/lineage. | Add tests for missing, empty, and tampered cards and for export failure/reuse of an existing output directory. Confirm failed exports cannot be mistaken for a completed export. |
| GOV-03 | Low | Coverage gap | ETA/duration disclosure is not consistently verified. | CLI labels duration as estimated and reports it unavailable without observed throughput; Command Center surfaces ETA values. No explicit UI/CLI wording regression test was found in the inspected paths. | Decide required wording in the requirement/acceptance criterion, then add a focused test. Do not change estimator behavior unless a defect is demonstrated. |
| GOV-04 | Medium | Coverage gap | Structured log context is not proven to meet the stated requirement. | Inspected formatters include timestamp, logger/severity, and message; run/stage identifiers exist in tracking/manifest paths, but are not automatically present in every log record. No single test was found proving the required fields together. | Clarify whether structured fields are normative for every event or only relevant events. Add a focused test for required timestamp, severity, run/stage IDs, and event context. |
| GOV-05 | Medium | Test adequacy gap | The doctor non-destructive test does not meaningfully detect filesystem mutation. | Existing test compares paths matching `pipeline/doctor.py` before and after; it does not snapshot datasets, artifacts, file contents, or unexpected files. | Run doctor against a disposable project containing sentinel files and artifacts; compare content hashes and filesystem inventory before/after. |
| GOV-06 | High, cross-cutting | Audit in progress | Some requirement-to-test mappings appear to claim more coverage than their tests establish. | Examples inspected include tests that only check a file exists, README text, or a source-code string for requirements about behavior, security, or data integrity. The structural validator confirms mapping completeness, not semantic adequacy. | Audit mappings in bounded batches. Classify each as behavioral coverage, partial coverage, existence/source smoke check, or missing test. Update only demonstrably inaccurate mappings and keep requirements `NOT_VERIFIED` until evidence exists. |
| GOV-07 | High, cross-cutting | Confirmed governance/test-mapping defect; overall behavior coverage varies by requirement | Several v1.1.0 mappings assign a requirement ID to a test whose assertions do not establish that requirement. This is a traceability/test-adequacy defect even when separate tests elsewhere cover some of the behavior. | In `tests/governance/test_requirement_acceptance.py` at review baseline `79990219e505c4531aa3a61fb9acbeff1cefbc00`, `test_REQ_SEC_002` checks log-tail bounds; `test_REQ_SEC_005` checks dependency metadata; `test_REQ_DATA_008` only checks that `hashlib.sha256` is callable; and `test_REQ_ART_003` searches source text for a dataset-card string. `test_REQ_REL_006` only checks that the tests directory exists. Separately, the same baseline contains dedicated behavioral tests such as `tests/test_runner_security_regressions.py`, `tests/test_command_center_credentials.py`, and `tests/test_release_gate.py`, including secret-redaction and fail-closed evidence cases. Therefore the confirmed defect is that the mapped test does not prove the requirement, not that the repository has no relevant tests at all. | Fix the test catalog so each requirement points to the test(s) whose assertions actually support it; where coverage remains missing, add a focused regression test. Keep the acceptance status `NOT_VERIFIED` until the correct tests are executed on the authoritative candidate. |
| GOV-08 | High | Confirmed source-snapshot/traceability mismatch; release candidate not selected | The package declares source snapshot `f06bbedb55e252cd7033c615733c5d2554a7d0aa`, but its mapped `tests/governance/test_requirement_acceptance.py` is absent at that revision. The review baseline is newer and contains the file. | At declared snapshot `f06bbedb55e252cd7033c615733c5d2554a7d0aa`, `pipeline/trainer/train.py` resolves but `tests/governance/test_requirement_acceptance.py` returns 404. The file exists at review baseline `79990219e505c4531aa3a61fb9acbeff1cefbc00`. Dedicated security and release-gate tests also exist at the review baseline. The 64-target checker result was run in the review worktree and cannot be represented as target validation at the declared snapshot. | Preserve `f06bbed...` as the package's declared source snapshot until the package owner explicitly revises it. Revalidate all exact catalog paths and test IDs against that snapshot; if the intended target is the review baseline instead, update the package's source-SHA metadata and rerun the structural/target checks there. Do not call either SHA a release candidate without an explicit candidate designation. |

## Verification evidence and limits

- Package structural validator: passed; 64 unique requirements, 64 complete traceability rows, and 64 unique test IDs.
- Test-target checker: passed; all 64 requirement-specific targets exist. It explicitly does not prove those tests pass or adequately test requirements.
- Selected existing tests: 88 passed, 1 warning. This was a selected test set, not the full repository suite.
- Separate governance acceptance suite: 64 passed, 1 warning.
- Selected-run coverage varied by module; the inspected run reported 44% overall and 6% for `pipeline/orchestrator.py`. These are scoped coverage figures, not full-suite coverage or proof of a product defect.
- Database schema comparison: historical v1 and current v2 schema SQL produced identical table and column definitions in disposable in-memory SQLite databases. No legacy database upgrade failure was reproduced.
- Traceability audit (bounded batch): inspected all 8 DATA, 7 ART, 8 OPS, 6 SEC, and 7 REL mappings in the v1.1.0 catalog against the acceptance test file in the review worktree. Multiple mapped assertions are existence checks or unrelated checks. This proves the mapping is inadequate; it does not establish that all relevant behavior lacks tests elsewhere in the repository.
- Cross-check at review baseline `79990219e505c4531aa3a61fb9acbeff1cefbc00`: dedicated `tests/test_runner_security_regressions.py` checks secret redaction in common encodings and launch-failure event payloads; `tests/test_command_center_credentials.py` checks encrypted storage/redaction and deletion; `tests/test_release_gate.py` checks unknown/missing evidence and package-validation failure; `tests/test_release_gate_contract.py` checks missing RC prerequisites. These are useful candidate test leads, not executed evidence for the declared `f06bbed...` snapshot or a release certification.
- Source-snapshot target check: at declared snapshot `f06bbedb55e252cd7033c615733c5d2554a7d0aa`, `pipeline/trainer/train.py` resolves but `tests/governance/test_requirement_acceptance.py` returns 404; that test file exists on current `main`. Therefore the package's exact-target-existence result, if run against a later worktree, is not evidence that the named targets exist at the declared snapshot.
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

Next: keep the package-declared source SHA distinct from the review baseline and validate the catalog at the declared SHA. Map P0 requirements to the dedicated behavioral tests that actually exercise them; add tests only where the cross-check shows a real gap. The repository review baseline contains useful security and release-gate tests, but they have not been executed as candidate-bound evidence for `f06bbed...`. Keep this work separate from production implementation fixes. Revisit schema migration only when evidence of a schema change or compatibility failure appears.


## GOV-09 — Catalog target inventory is not valid for the declared source snapshot

**Priority:** High for governance-package validity  
**Status:** Confirmed source/target mismatch; requirement status unchanged  
**Evidence revision:** `f06bbedb55e252cd7033c615733c5d2554a7d0aa`  
**Review baseline (not substituted):** `79990219e505c4531aa3a61fb9acbeff1cefbc00`

A recursive Git tree query against the exact declared source SHA confirms that:
- `tests/governance/test_requirement_acceptance.py` is absent.
- `tests/test_runner_security_regressions.py` is absent.
- The export implementation path is `scripts/export_gguf.py`; `pipeline/export_gguf.py` is absent.
- `tests/test_command_center_credentials.py`, `tests/test_release_gate.py`, and `tests/test_release_gate_contract.py` are present at that SHA. Their presence establishes only that the files exist, not that their tests pass or satisfy every mapped requirement.

The earlier structural result (64 requirements, 64 traceability rows, 64 unique test IDs, and all targets found) was run in the separate review worktree at `79990219e505c4531aa3a61fb9acbeff1cefbc00`. It must not be reported as an exact-target-existence pass for `f06bbed...`. The package-declared source SHA remains unchanged; this review does not silently substitute the review baseline or designate either SHA as a release candidate.

### Concrete mapping corrections to propose

| Requirement | Inadequate catalog assertion / mapping | Correct verification target |
|---|---|---|
| `REQ-SEC-001` safe subprocess handling | Import/path traversal assertion does not establish safe command construction or executable selection. | Test subprocess invocation with hostile arguments; assert argument-vector use / no unsafe shell interpolation and expected executable selection. |
| `REQ-SEC-002` path/archive safety | Log-tail bound test is unrelated to traversal and malformed archive handling. | Adversarial tests for traversal paths, malformed manifests/archives, and unsafe model/card paths, with no writes outside the intended root. |
| `REQ-SEC-003` secret handling | Checking whether a real `.env` file exists does not prove secrets are excluded from logs/errors/artifacts. | Inject canary secrets through supported failure paths; assert absence from captured logs, user-facing errors, cards, and release outputs. Use the dedicated credential/redaction tests where applicable. |
| `REQ-SEC-005` external effects (if present in the catalog's versioned requirement set) | Dependency metadata does not prove no unapproved network transfer occurs. | Instrument/deny network access and verify local-only workflows make no outbound calls; separately test any explicitly invoked transfer is disclosed. |
| `REQ-DATA-008` schema evolution (catalog label must be checked against the actual requirement text) | `callable(hashlib.sha256)` proves neither schema compatibility nor evolution behavior. | Test supported prior schema fixtures, explicit version detection, migration/compatibility outcomes, and preservation of data; if the requirement is actually streaming/bounded-memory, replace this with a representative bounded-memory/resource test instead. |
| `REQ-ART-003` artifact integrity | Grepping source for a dataset-card string does not test missing, partial, inconsistent, or corrupt artifacts. | Remove/truncate/tamper with artifacts and assert verification reports failure without declaring a complete export. |
| `REQ-REL-005` release gate (catalog row previously described as `REQ-REL-006`; verify the package's exact requirement ID before editing) | Checking that a tests directory exists does not show the release gate rejects missing/unknown evidence or unresolved blockers. | Exercise the actual release gate with required evidence missing, unknown, malformed, and failed; assert non-pass status and no certification claim. |
| `REQ-REL-006` performance/resource claims in the requirements document retrieved from the library | A generic test-directory check is not a claim-to-measurement audit. | Enumerate advertised claims and require linked measurements, configuration, hardware, and conditions; fail on unsupported claims. |

The IDs in the catalog and the IDs in the requirements document must be reconciled before any row is edited. In particular, do not carry forward an ID based solely on a remembered or similarly named requirement: the requirement text and versioned ID are authoritative.

### Disposition and exit condition

1. Preserve the package-declared SHA as the target until the package owner explicitly approves a different source identity.
2. Rebuild a target inventory from the tree at that SHA and mark absent targets as **MISSING AT DECLARED REVISION**, not as passing.
3. For each mapped test, record whether it is present, behaviorally relevant, and executed; these are separate checks.
4. Propose a corrected mapping table against the exact package requirement IDs. Do not edit the package's normative requirements or change any of the 64 statuses from `NOT_VERIFIED` as part of this review-log update.
5. Do not claim release certification or product implementation failure from a catalog mapping defect alone.


## GOV-09 clarification — Missing catalog targets are declared test debt, not a false pass

The package's own `README.md` says `check_test_coverage.py` is expected to fail until missing tests are implemented. `TEST_CASE_CATALOG.csv` marks every row `REQUIRED_UNTIL_EXACT_COVERAGE_CONFIRMED`, and every verification status is `NOT_VERIFIED`. `TRACEABILITY.md` explicitly says proposed targets prefixed `ADD REQUIRED:` do not exist. Therefore, the absence of `tests/governance/test_requirement_acceptance.py` at the declared source SHA is a confirmed missing-test condition, but **not evidence that the package falsely claims the tests already pass**.

There is still a clarity defect: the catalog's `required_exact_test_target` field gives each missing test as a concrete `path::function` without an explicit `ADD REQUIRED:` marker, even though the expected-result text says the executable case must be added. This is easy to misread as an existing test reference. A package correction should mark planned targets as `ADD REQUIRED: tests/governance/test_requirement_acceptance.py::test_REQ_...` (or split existing target and required new target into separate fields), while keeping the fail-closed checker able to parse the chosen format.

The checker logic is intentionally simple: it splits every target on `::`, checks the file, and looks for an exact function identifier. Against the declared source tree, the shared target file is absent, so all 64 catalog targets are missing at that revision. This is the expected fail-closed coverage-gap result, not a test run and not proof the product features are absent. Existing test areas listed in the catalog are candidate context only; they do not substitute for the requirement-specific targets until inspected for behavioral adequacy.

### Corrected requirement-ID reconciliation for the examples in GOV-09

The v1.1.0 package's own `REQUIREMENTS.md` is authoritative for the requirement names and IDs. The relevant IDs are:
- `REQ-SEC-001` — Least privilege.
- `REQ-SEC-002` — Path safety.
- `REQ-SEC-003` — Secret handling.
- `REQ-SEC-005` — Explicit external effects.
- `REQ-DATA-008` — Schema evolution.
- `REQ-ART-003` — Dataset documentation.
- `REQ-REL-005` — Revision/package identity.
- `REQ-REL-006` — Honest release gate.

**Correction to the earlier GOV-09 table:** `REQ-REL-006` is *Honest release gate*, not a performance/resource-claims requirement. A correct behavioral test should feed the release gate missing, blocked, failed, or not-tested mandatory evidence and assert that certification is refused. `REQ-REL-005` should instead test binding the evidence to the exact source revision, build inputs, package identity, and relevant dependency versions. Performance/resource-claim auditing belongs only under the requirement ID actually governing those claims in the approved v1.1.0 package; it must not be assigned to `REQ-REL-006`.

For `REQ-DATA-008`, the package's requirement is schema evolution, so tests must exercise versioned persistent records and compatibility/migration behavior. A hash-function-presence check is not sufficient. For `REQ-ART-003`, the requirement is dataset documentation; verify the exported model has the required model-specific card and that export validation fails when the card is missing. For the security rows, preserve their package-defined titles and verify the relevant behavior separately: least privilege, path containment, secret non-disclosure, and explicit/bounded external effects. A generic assertion copied across those rows is not adequate evidence.

### Exit condition

Before changing the v1.1.0 package itself, prepare a focused package patch that (1) marks all not-yet-implemented exact test targets unambiguously as required additions, (2) corrects the `REQ-REL-005` / `REQ-REL-006` verification distinction, (3) retains the 64 `NOT_VERIFIED` statuses, and (4) reruns the package structural validator and fail-closed coverage checker. The source SHA remains `f06bbedb55e252cd7033c615733c5d2554a7d0aa` unless the owner explicitly approves a replacement.
