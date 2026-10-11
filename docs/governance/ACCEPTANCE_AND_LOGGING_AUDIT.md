# Acceptance Catalog Review and Security Sink Audit

**Review date:** 2026-10-11  
**Branch:** `governance/acceptance-foundation-v1`  
**Status:** Static review only; execution evidence not available in this environment.

## Scope and limits

Reviewed the 64 exact test target names in `tests/governance/test_requirement_acceptance.py`, the supplemental operational tests, runner subprocess logging, credential storage, and repository workflow configuration through GitHub file access. The repository's canonical governance requirement catalog and coverage-checker source were not available at the expected repository paths. The attached governance ZIP is a specification package, not buildable source. Consequently, this document is a disposition triage, not a claim that all 64 requirements were mapped to their authoritative acceptance criteria.

## Acceptance target review

### Behavioral tests already present (retain, then execute)
- `UI-001`, `UI-002`: HTTP responses and rendered app surface.
- `WF-003`: runner API availability only; lifecycle behavior is supplemental.
- `WF-008`: concurrent-start guard, but its fake thread never executes; replace with a barrier-controlled thread/process lifecycle test.
- `DATA-003`, `DATA-005`, `DATA-007`: artifact provenance mismatch, atomic JSON round trip, store create/read/path rejection.
- `ART-001`, `ART-006`: tamper detection and digest correctness.
- `OPS-003`: nonzero worker exit causes error state and failure event.
- `OPS-004`: encrypted credential storage/reveal/delete contract.
- `SEC-001`, `SEC-002`, `SEC-004`: traversal rejection, bounded log tail, environment-variable validation.

### Structural or shallow targets requiring stronger behavior or an explicit spec-based disposition
- `UI-003`, `UI-004`, `UI-006`: file existence alone does not establish template/API/authorization behavior.
- `UI-005`: line-count limit is an implementation detail unless mandated by the spec.
- `ENV-001` through `ENV-004`, `ENV-006`: parsing or checking a file exists is not the same as executing documented doctor/bootstrap contracts.
- `WF-001`, `WF-002`, `WF-005` through `WF-007`: presence/string checks should become parsed configuration validation and CLI behavior.
- `DATA-001`, `DATA-002`, `DATA-004`, `DATA-006`, `DATA-008`: docs/source presence or checking that hashlib exists does not test a schema, identity, or checksum contract.
- `ML-001` through `ML-008`: most are file/source-presence checks; test actual profile parsing, resource estimates, evaluation records, and comparability rules.
- `ART-002` through `ART-005`, `ART-007`: documentation/source presence does not prove export-card validity, paired artifact integrity, or dataset-card enforcement.
- `OPS-001`, `OPS-002`, `OPS-005` through `OPS-008`: docs, substring, and workflow file checks do not exercise health, retention, structured logging, or event contracts.
- `SEC-003`, `SEC-005`, `SEC-006`: tracked-tree scan, lockfile presence, and policy-file presence do not prove repository history is secret-free, dependency resolution is reproducible, or controls are enforced.
- `REL-001` through `REL-007`: workflow/source/file existence and version presence are insufficient; test actual gate invocation, clean-clone behavior, failure exit status/report consistency, package version identity, and layered test discovery.

This review identifies targets for replacement but does not silently rewrite expected behavior without the canonical catalog. Requirement IDs must remain stable. Each replacement should link its assertion to the exact normative statement and test observable behavior.

## Logging and secret exposure sink audit

### Confirmed code path to cover
- `command_center/runner.py` receives child stdout and writes it to a log file. The branch's redactor covers the known injected credential values and several encodings before that file write. This is only a single sink and only values known to the redactor.

### Required sink inventory
1. Worker stdout/stderr and file logs, including multiline and chunk-split values.
2. Event-store payloads emitted on success/failure/cancellation/recovery.
3. Exception messages and tracebacks from credential retrieval, subprocess creation/wait, file writes, JSON parsing, and API handlers.
4. Structured logger fields and serialization of nested dictionaries/lists.
5. API responses, health/diagnostic output, console output, and test failure diagnostics.
6. Credential persistence, temporary files, atomic-write staging files, and crash-recovery state.
7. CI logs and generated test/evidence artifacts.

### Risk and disposition
- **Known-secret substitution is defense in depth**, not a complete policy. Base64/URL/JSON variants, Unicode escapes, nested structures, partial/chunked output, and values not injected by the credential store may bypass string replacement.
- Prefer allowlisted structured fields and never serialize credential-bearing environment maps. Redact exception context before persistence, not only at presentation.
- Test synthetic canary values at every sink. Assert absence of raw and enumerated encodings from files, event records, captured logs, API bodies, exception text, and serialized structured fields.
- Do not run scans on real credentials or put secret-bearing fixtures in assertion messages.

## Coverage checker and regression evidence

The coverage checker source was not found at `scripts/check_test_coverage.py` or repository-root `check_test_coverage.py` through the current repository file API. The separately attached governance package contains `check_test_coverage.py`, but this environment cannot execute the ZIP or clone repository contents because outbound DNS failed. No checker exit code is available.

No comparable base-versus-branch regression results were obtained. Do not infer test results from commit status, code review, or the presence of test functions.

## Required reproducible run

On a machine with repository access, record:
- base SHA and branch SHA;
- exact Python and dependency environment;
- coverage-checker command and stdout/stderr/exit code;
- identical pytest commands on base and branch;
- total passed/failed/skipped/error counts;
- failure IDs and stack traces, classified as pre-existing, regression, environment/setup, or flaky;
- CI workflow/run IDs, job IDs, platform/Python matrix, artifact links, and final conclusion.

A valid baseline comparison requires the same commands and equivalent dependency setup on both SHAs. Report deltas, not just two independent green/red labels.
