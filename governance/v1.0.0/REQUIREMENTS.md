# ML-Framework System Requirements

**Document ID:** MLF-GOV-003  
**Version:** 1.0.0  
**Status:** Approved project baseline  
**Prepared:** 2026-10-11  
**Approval:** Approved by product owner on 2026-10-11

## 1. Purpose and interpretation

This document defines observable obligations for ML-Framework. It is a requirements baseline, not evidence that the current implementation satisfies the requirements. Each requirement must be traced to design, implementation, and revision-specific verification evidence. Unless explicitly marked otherwise in a controlled requirements register, requirements below are mandatory for the applicable supported feature or release claim.

## 2. Requirement conventions

Requirement IDs are stable identifiers. Verification may use inspection, analysis, test, demonstration, or a combination. A requirement is **verified** only when evidence identifies the tested revision and environment and demonstrates the stated outcome. Missing evidence means unverified, not passed. Unsupported features must be identified as unsupported rather than presented as available.

## 3. Environment and installation

- **REQ-ENV-001:** Document supported operating systems, Python/runtime versions, and mandatory external tools.
- **REQ-ENV-002:** Preflight must distinguish required dependencies from optional capabilities.
- **REQ-ENV-003:** Installation instructions must work from a clean checkout without undeclared developer-specific files or caches.
- **REQ-ENV-004:** ZIP/source-download installation must be verified if it is claimed as supported.
- **REQ-ENV-005:** Startup failures must identify the failed prerequisite and a safe corrective action where known.
- **REQ-ENV-006:** Hardware and resource guidance must state its limits and must not promise that a workload will fit or converge.

## 4. Command Center

- **REQ-UI-001:** Provide one browser-based Command Center as the primary operator interface.
- **REQ-UI-002:** Show application health, detected capabilities, prerequisites, and verification status accurately.
- **REQ-UI-003:** Core operator actions must provide visible success, failure, or in-progress outcomes.
- **REQ-UI-004:** Run status, stage progress, logs, metrics, and artifacts must refer to the correct stable run identity.
- **REQ-UI-005:** Unavailable, unsupported, or unverified features must not be represented as proven capabilities.

## 5. Workflow and data integrity

- **REQ-WF-001:** Validate workflow configuration and prerequisites before starting work.
- **REQ-WF-002:** Give each run a stable identifier and record relevant inputs, configuration, stages, outputs, and provenance.
- **REQ-WF-003:** Reject or explicitly handle invalid state transitions.
- **REQ-WF-004:** Cancellation, timeout, subprocess failure, and nonzero exit must produce accurate terminal states.
- **REQ-WF-005:** Incomplete outputs must never be reported as successful completion.
- **REQ-WF-006:** Critical state and manifests must use atomic writes or an equivalent documented consistency strategy.
- **REQ-WF-007:** Recovery and retry behavior must not silently duplicate, corrupt, or misrepresent work.
- **REQ-WF-008:** Pipeline stage names and semantics must be consistent across configuration, execution, persisted records, and UI.

## 6. Data preparation and model workflows

- **REQ-DATA-001:** Record input identity and source for each run.
- **REQ-DATA-002:** Cleaning and deduplication behavior must be explicit and testable.
- **REQ-DATA-003:** Weighting, tokenization, and sharding settings and outputs must be traceable where those stages are enabled.
- **REQ-DATA-004:** Tokenizer and shard manifests must identify the artifacts they describe and detect mismatches.
- **REQ-DATA-005:** Invalid or incomplete preparation outputs must fail validation before downstream use.
- **REQ-DATA-006:** Provenance must connect the input/preparation artifacts to downstream training outputs.
- **REQ-ML-001:** Declare supported model, configuration, backend, and hardware combinations.
- **REQ-ML-002:** Record relevant training configuration, software/backend versions, random seeds where applicable, and metrics.
- **REQ-ML-003:** Resource estimates must be labeled estimates and disclose material constraints.
- **REQ-ML-004:** Validate metrics for type, finiteness, and expected structure before treating them as valid evidence.
- **REQ-ML-005:** Explain metric meaning and limitations.
- **REQ-ML-006:** Compare runs only when the comparison basis and incompatibilities are disclosed.
- **REQ-ML-007:** Smoke-test completion must not be described as proof of convergence, quality, or generalization.

## 7. Artifacts and exports

- **REQ-ART-001:** Exported artifacts must retain a link to their originating run and relevant inputs/configuration.
- **REQ-ART-002:** Validate each supported export format with format-appropriate checks.
- **REQ-ART-003:** Required metadata and model/dataset documentation must accompany the export as a logical unit.
- **REQ-ART-004:** Integrity manifests must detect missing or mismatched export components.
- **REQ-ART-005:** Runtime compatibility claims must be tested against named runtimes or formats.
- **REQ-ART-006:** Unsupported export targets must fail clearly without claiming a usable artifact.
- **REQ-ART-007:** Export failures must preserve diagnostic evidence and avoid presenting partial output as complete.

## 8. Operations, security, and privacy

- **REQ-OPS-001:** Known failures must produce actionable diagnostic context.
- **REQ-OPS-002:** Destructive operations must validate targets and communicate impact; unsafe paths must be rejected.
- **REQ-OPS-003:** Critical persistent writes must resist partial-write corruption.
- **REQ-OPS-004:** Logs and diagnostic bundles must redact secrets and sensitive values.
- **REQ-OPS-005:** Diagnostic collection must disclose included information and avoid unintended uploads.
- **REQ-OPS-006:** Backup/restore and schema migration must be tested where persistent user data is promised.
- **REQ-OPS-007:** Cleanup must respect declared retention rules and avoid deleting unrelated data.
- **REQ-OPS-008:** External services, network access, and data transfer must be disclosed and governed by explicit configuration/consent.

## 9. Release and evidence

- **REQ-REL-001:** Release evidence must identify the exact source revision and tested package.
- **REQ-REL-002:** Mandatory tests and security checks must pass under the approved release plan.
- **REQ-REL-003:** Clean-environment installation and core operator workflows must be tested for claimed supported environments.
- **REQ-REL-004:** Installation and startup must not depend on undeclared local state.
- **REQ-REL-005:** Artifact export and associated documentation must pass integrity validation.
- **REQ-REL-006:** Release claims must not exceed available verification evidence.
- **REQ-REL-007:** Release records must distinguish pass, fail, blocked, skipped, and not tested.

## 10. Baseline authority

This requirements baseline was approved by the product owner on 2026-10-11. Changes require recorded rationale, impact analysis, approval, and updates to traceability and verification evidence. Approval establishes the governing intent; it does not certify implementation compliance.