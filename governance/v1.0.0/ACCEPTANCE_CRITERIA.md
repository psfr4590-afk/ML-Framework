# ML-Framework Acceptance Criteria

**Document ID:** MLF-GOV-007  
**Version:** 1.0.0  
**Status:** Approved acceptance baseline  
**Prepared:** 2026-10-11  
**Approval:** Approved by product owner on 2026-10-11

## 1. Purpose

This document defines acceptance rules. It separates implementation completion from verified behavior and feature acceptance from release certification. These criteria govern the product; they do not certify the current repository.

## 2. General acceptance rules

A deliverable is acceptable only when its approved requirements are identified; observable behavior matches them; relevant positive, negative, and boundary cases are tested; errors and failure states are safe and understandable; security, privacy, resource, and data-integrity implications are addressed; documentation is updated; evidence identifies the tested revision and environment; and known limitations are recorded. Code review, a successful build, or a passing unit-test count alone is insufficient.

## 3. Feature-level acceptance

Define before implementation: user outcome, preconditions/support environment, normal behavior, invalid-input behavior, cancellation/retry/recovery, persistence/provenance impact, security/privacy impact, resource constraints, verification cases/evidence, and documentation changes. All mandatory criteria must pass. A non-applicable criterion needs a rationale. Untested criteria remain unverified.

## 4. Core product acceptance

### 4.1 Installation and startup
- Document supported prerequisites and the support envelope.
- Install and launch successfully in a clean supported environment.
- Test ZIP/source-download installation if claimed as supported.
- Identify missing required dependencies separately from optional capabilities.
- Avoid dependencies on undeclared local files or developer-specific caches.

### 4.2 Command Center
- The browser Command Center is the single primary operator interface.
- Core actions show visible outcomes and meaningful errors.
- UI status matches authoritative run state.
- Logs, metrics, stage state, and artifacts correlate to the correct run.
- Unavailable or unverified features are not presented as proven.

### 4.3 Workflow integrity
- Validate configuration and prerequisites before execution.
- Give each run stable identity and traceable inputs/outputs.
- Reject or explicitly handle invalid state transitions.
- Cancellation, timeout, subprocess failure, and nonzero exit produce accurate states.
- Incomplete output is never reported as success.
- Injected write failures do not leave partial manifests that appear valid.

### 4.4 ML run evidence
- Record relevant configuration, input identity, backend/software versions, and metrics.
- Validate metrics and document their interpretation.
- State resource guidance as estimates with uncertainty.
- Tie support claims to the declared model/configuration matrix.
- Do not present a smoke test as evidence of convergence or model quality.

### 4.5 Artifact and export integrity
- Supported exports pass format-specific validation.
- Required metadata and model/dataset documentation accompany the artifact as one logical export unit.
- Integrity checks detect missing or mismatched components.
- Provenance identifies the originating run and relevant inputs/configuration.
- Compatibility claims are tested against named runtimes/formats.

### 4.6 Security and privacy
- Prevent path traversal and unintended destructive operations.
- Keep secrets out of normal logs and redact them in diagnostics.
- Disclose external transfers and services.
- Document dependency/executable provenance appropriate to the release.
- Fail safely on unsafe or unsupported artifact inputs.

### 4.7 Operations and recovery
- Known failures produce useful diagnostic context.
- Diagnostic bundles disclose contents and redact sensitive values.
- Backup/restore works for persistent data the product promises to preserve.
- Cleanup previews impact and respects retention rules.
- Recovery instructions state what data or progress cannot be recovered.

## 5. Release acceptance

A release candidate is eligible for certification only when the candidate revision/package is fixed; mandatory static, unit, integration, end-to-end, security, and packaging checks pass as required; mandatory supported environments have evidence; clean-environment installation and launch pass; core operator workflows pass end to end; artifact exports and documentation pass integrity checks; no unresolved critical/high-severity defect remains under the approved policy unless a permitted and documented risk acceptance applies; traceability is complete; evidence is retained; and release notes accurately state supported capabilities, limits, and known issues.

## 6. Hard NO-GO conditions

Withhold release certification if any mandatory criterion is failed, blocked, or untested; the tested package cannot be tied to the declared source revision; clean installation or a mandatory core workflow fails; provenance or artifact/documentation pairing is missing or mismatched; security/data integrity violates an approved requirement; claims exceed evidence; or required evidence is missing or unreviewable. A high aggregate test count cannot turn a hard NO-GO into a pass.

## 7. Waivers and exceptions

A waiver must identify the criterion, reason, affected users, risk, mitigation, expiry/review date, and approving authority. Hard NO-GO conditions are not waivable unless governing release policy explicitly permits the exception and the release is not misrepresented as fully certified.

## 8. Evidence requirements

Retain source revision and working-tree state, build/package hash and inputs, environment/dependency versions, test commands/results, relevant failure/recovery logs, export manifests and validation results, traceability status, and known limitations. Distinguish passed, failed, blocked, skipped, and not run.

## 9. Acceptance decision record

For each milestone/release, record candidate/version and exact revision; covered criteria and requirements; a status summary using `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, and `NOT RUN`; defects/deviations/waivers; evidence locations; decision, approver, and date.

## 10. Baseline authority

These criteria were approved by the product owner on 2026-10-11. Approval establishes the acceptance baseline but does not mean existing features have passed; implementation must be evaluated independently.