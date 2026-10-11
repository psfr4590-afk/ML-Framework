# Governance v1.1.0 implementation plan

This plan is a companion to the supplied governance package. It is not a substitute for importing the complete package or for the normative requirement catalog.

## Gate 0 — Preserve source and establish candidate identity

- [ ] Import every file from the supplied `v11/` directory, including `history/`, both checksum files, the CSV catalogs, and both Python validators.
- [ ] Keep historical v1.0 documents byte-for-byte intact.
- [ ] Verify `SHA256SUMS.txt` and `SHA256SUMS-HISTORY.txt` against the imported files.
- [ ] Record the exact tested commit SHA and Python version for every verification run.

## Gate 1 — Establish traceability

- [ ] Run `python governance/v11/validate_governance.py` after package import.
- [ ] Run `python governance/v11/check_test_coverage.py --repo-root .`.
- [ ] For every reported missing test, inspect the corresponding catalog row and add an executable acceptance test with an objective assertion.
- [ ] Do not satisfy the checker by adding placeholder functions, skipped tests, or tests that merely assert source text unless the requirement itself is explicitly structural.

## Gate 2 — Close behavioral and security gaps

The supplied audit flags the following decisions or evidence as unresolved; the exact requirement IDs and acceptance criteria in the imported normative catalog control implementation:

- Candidate-bound clean-install evidence across the claimed OS, Python, GPU/CUDA, and native-tool combinations.
- Functional, security, failure-recovery, and data-integrity acceptance coverage beyond structural tests.
- Approved dataset-card and model-card contracts.
- Evaluation thresholds and evidence supporting model-quality claims.
- Resource limits, retention policy, and recovery objectives.
- Alignment between application release versioning and governance specification versioning.

Resolve each with code/tests or an explicit approved waiver/decision. Do not turn missing evidence into a pass.

## Gate 3 — Run repository verification

Use the repository's own canonical instructions and inspect `pyproject.toml`, test configuration, and `docs/verification/VERIFICATION.md` before selecting commands. At minimum, record results for the existing test suite, lint/static checks, governance validators, and applicable release verification. The native RC gate must be run in an appropriate environment before any native-release claim.

## Gate 4 — Review

- [ ] Attach reproducible command output and candidate SHA to the PR.
- [ ] Leave platform support as `NOT_VERIFIED` where candidate-specific evidence is absent.
- [ ] Keep the PR draft until Gates 0–3 have evidence.
- [ ] Do not merge without review.

## Known current limitation

At the time this plan was added, only the integration scaffold and repository mapping addendum were committed. The complete v1.1.0 source package had not been imported, and no new application acceptance tests or full-suite results were claimed.
