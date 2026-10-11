# ML-Framework Governance Package v1.1.0 Integration

> Status: integration scaffold only. This file does not assert that the repository is compliant.

## Source of truth

The intended source package is `ML-Framework-governance-package-v1.1.0-repository-mapped.zip`, supplied with the project. The package includes governance requirements, traceability, support/compatibility matrices, a test-case catalog, historical baselines, decision records, and validation utilities.

## Required integration sequence

1. Import the complete v1.1.0 package without silently rewriting its historical baseline or decision records.
2. Preserve source checksums and run the package's structural validator.
3. Map each requirement to an existing implementation path and one or more executable tests. Record unsupported, ambiguous, and unimplemented requirements explicitly rather than inferring compliance.
4. Implement missing behavior in small, reviewable changes with regression tests.
5. Run the package's coverage/traceability checker against the repository and fix gaps. A passing structural validator alone is not evidence of implementation compliance.
6. Run the repository's existing test suite and all applicable governance checks; record exact commands and results.
7. Open a draft pull request against `main`; do not merge automatically.

## Safety and evidence rules

- This work must remain on an isolated branch until reviewed.
- Do not change the upstream default branch directly.
- Do not mark a requirement implemented without code evidence and a passing test.
- Do not fabricate test results or convert missing evidence into a pass.
- Keep baseline/history files intact; add new decisions rather than overwriting prior decisions.
- The full source archive must be imported before this scaffold can be considered a package integration.

## Current evidence

- The v1.1.0 package's internal structural validator was reported to pass in the local project environment.
- The package itself warns that structural validation does not establish application compliance.
- The repository audit identified missing requirement-specific acceptance tests.
- The complete archive has not yet been committed to this branch, and repository-wide compliance has not been verified.

## Acceptance criteria for this integration

- [ ] All source package files are present and checksum-verified.
- [ ] Requirements are mapped to implementation and executable tests.
- [ ] Coverage/traceability checks pass, or every remaining gap is explicitly documented.
- [ ] Existing project tests pass.
- [ ] A reviewer can reproduce the validation from documented commands.
- [ ] The pull request remains unmerged until reviewed.
