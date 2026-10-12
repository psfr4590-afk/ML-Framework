# ML-Framework Requirements Traceability

**Document ID:** MLF-GOV-006  
**Version:** 1.0.0  
**Status:** Approved traceability baseline  
**Prepared:** 2026-10-11  
**Approval:** Approved by product owner on 2026-10-11

## 1. Purpose

This register connects product outcomes and requirements to architecture, implementation, and verification evidence. It is a living governance artifact. A mapping is not proof of compliance: implementation and evidence fields must be populated from repository inspection and revision-specific test results.

## 2. Traceability rules

- Keep requirement IDs stable; retire or replace them with a recorded rationale.
- Map each requirement to one or more architectural responsibilities and implementation paths.
- Map each mandatory requirement to explicit verification cases.
- Record the tested commit, environment, result, and evidence location.
- Distinguish `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, and `NOT RUN`.
- Treat missing implementation or verification mapping as an orphan requiring review.
- Do not infer compliance from aggregate test counts, code presence, or a successful build.

## 3. Product-outcome traceability

| Product outcome | Requirement families | Primary architecture areas | Required evidence |
|---|---|---|---|
| Install and launch cleanly | REQ-ENV-001–006, REQ-REL-003–004 | Runtime, packaging, release verification | Clean install/start logs for each claimed environment |
| Understand capability and limits | REQ-UI-002, REQ-UI-005, REQ-ML-001–003 | Command Center, runtime detection | UI/API contract tests and capability probes |
| Operate through one interface | REQ-UI-001–004, REQ-WF-001–008 | Command Center, API, orchestrator | Real browser-to-backend vertical slices |
| Trace inputs to outputs | REQ-WF-002, REQ-DATA-001–006, REQ-ART-001–004 | Stage workers, persistence, provenance | Run manifests, hashes, lineage validation |
| Fail and recover safely | REQ-WF-003–007, REQ-OPS-001–007 | Orchestrator, persistence, operations | Injected failure, cancellation, restart and recovery tests |
| Interpret model results | REQ-ML-004–007 | Training, evaluation, Command Center | Validated metrics and documented evaluation results |
| Export usable artifacts | REQ-ART-001–007 | Exporters, runtime integration | Format checks, metadata pairing, target-runtime tests |
| Verify releases | REQ-REL-001–007 | Release verification and packaging | Candidate identity, gate results, evidence bundle |

## 4. Requirement-level mapping template

Maintain one row per requirement in the implementation tracking register using these fields:

| Field | Meaning |
|---|---|
| Requirement ID | Stable ID from `REQUIREMENTS.md` |
| Architecture | Component or boundary responsible |
| Implementation | File/module, or explicit `NOT FOUND` |
| Verification | Test name, command, or procedure |
| Evidence | URL/path plus tested revision and environment |
| Status | `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, `NOT RUN` |
| Owner / date | Person responsible and last review date |
| Gap / action | Missing mapping, defect, or follow-up |

## 5. Coverage expectations

Every mandatory requirement needs implementation mapping and a verification method. Every claimed implemented capability should map to an approved requirement or a documented rationale. Tests that protect a security or reliability invariant should map to the requirement/risk they cover. Release claims must map to evidence for the exact candidate.

## 6. Change impact analysis

When a requirement changes:
1. Record rationale and approval.
2. Identify affected architecture responsibilities and decision records.
3. Identify implementation and persistent-schema impacts.
4. Add or update verification cases.
5. Update documentation and support claims.
6. Re-run affected verification and retain evidence.
7. Update this register and inspect for newly orphaned requirements or tests.

Changes to serialization, manifests, run lifecycle, artifact formats, or persistent schemas require explicit migration and compatibility analysis.

## 7. Orphan detection

Review regularly for approved requirements without implementation mappings; implemented features without approved rationale; requirements without verification; tests without a mapped requirement or risk; release claims without evidence; artifacts without provenance; and architecture decisions without verification impact. Orphans are reviewed, not automatically deleted or accepted.

## 8. Release traceability rule

Every release report must identify the exact candidate revision and package and summarize mandatory requirements as verified, failed, blocked, deferred, or not tested. Aggregate test counts do not substitute for requirement-level evidence.

## 9. Baseline authority

This traceability baseline was approved on 2026-10-11. Keep it current as part of development and review, not as a last-minute release chore.