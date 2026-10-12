# ML-Framework Architecture Baseline

**Document ID:** MLF-GOV-004  
**Version:** 1.0.0  
**Status:** Approved architecture baseline  
**Prepared:** 2026-10-11  
**Approval:** Approved by product owner on 2026-10-11

## 1. Purpose

This document defines intended architectural responsibilities and boundaries. It describes the target design, not a claim that every boundary is already implemented. Deviations in the repository must be documented and evaluated against requirements, security, data integrity, and operator workflows.

## 2. Architectural principles

- Local-first execution by default; disclose external services and network transfers.
- One browser Command Center is the canonical operator interface.
- Explicit boundaries between presentation, orchestration, stage execution, persistence, and artifact handling.
- Durable state must be validated and written atomically or with an equivalent consistency strategy.
- Capabilities and release claims require evidence tied to exact revisions and environments.
- Components should be testable independently and through end-to-end vertical slices.

## 3. Logical components

### 3.1 Browser Command Center

Owns operator presentation: health/readiness, supported capability information, configuration, run control, status, logs, metrics, and artifact visibility. It must not invent state independently of the authoritative backend. UI actions should call explicit backend operations and render their actual results.

### 3.2 Application/API boundary

Provides validated operations between the browser and the application services. It is responsible for input validation, consistent error responses, access to authorized operations, and preventing UI-level assumptions from bypassing backend invariants.

### 3.3 Pipeline orchestrator

Coordinates a run's lifecycle and ordered stages. It assigns or propagates stable run identity, checks prerequisites, records stage transitions, handles cancellation/failure, and ensures a failed or incomplete stage cannot be recorded as a successful run. Stage execution details should remain in their responsible modules.

### 3.4 Stage workers

Implement data intake and preparation, cleaning, deduplication, weighting, tokenization, sharding, training, evaluation, and export only where supported. Each stage declares inputs, outputs, configuration, validation, and failure behavior. Stage naming and semantics must be consistent across configuration, execution, and persisted evidence.

### 3.5 Persistence and provenance

Owns durable run records, stage records, manifests, configuration snapshots, metrics, and artifact references. Use stable schemas, explicit migrations where needed, and atomic writes or an equivalent documented consistency mechanism. Provenance should connect source inputs through preparation artifacts and training to exports.

### 3.6 Runtime and external tools

Wraps optional backends and external executables such as native inference runtimes. Detect and report missing or incompatible dependencies before launching expensive work. Never represent a detected binary or configured backend as verified inference capability without a successful test.

### 3.7 Release verification

Runs static checks, tests, clean-environment setup, UI/backend probes, native bootstrap and inference, export/runtime checks, and provenance validation as required by the release profile. Its report records the exact source revision, environment, package identity, commands, outcomes, and evidence paths.

## 4. Data and state flow

A supported run should be traceable through the following conceptual chain:

`source inputs → normalized/cleaned data → deduplicated/weighted data → tokenizer → shards → training run/checkpoint → evaluation → exported artifact`

Not every workflow uses every stage. Each enabled transition must validate its predecessor's output and record identities/hashes where practical. A later artifact must not be treated as valid merely because a file exists.

## 5. State and failure semantics

- State transitions must be explicit and validated.
- Persisted status must reflect authoritative process and stage outcomes.
- Cancellation, timeout, exceptions, missing outputs, and nonzero subprocess exits must not become success states.
- Critical manifests must not be left as partially written valid-looking files.
- Retries must define whether prior outputs are reused, replaced, or preserved.
- UI/backend disagreement is a defect; the UI should expose unknown or stale state rather than guess.

## 6. Security boundaries

Validate filesystem paths at the point of use; constrain destructive operations to declared roots; redact credentials and sensitive paths in logs; avoid unsafe deserialization; pin or verify external artifacts where feasible; and document network use. Model files and data inputs are untrusted until validated. A local-first design is not, by itself, a security guarantee.

## 7. Resource management

The system should estimate CPU, RAM, VRAM, storage, and runtime needs where practical. Estimates must be labeled as estimates. It must expose material constraints and fail safely when required dependencies or resources are unavailable. It must not promise that a workload fits merely because a preflight check passes.

## 8. Verification strategy

Test components in isolation, contract boundaries, persistence/failure behavior, and complete UI-to-backend workflows. Native runtime and export claims require real runtime evidence, not only mocked tests. Clean-clone acceptance must start from a fresh checkout without relying on developer-specific state.

## 9. Architecture changes

Changes affecting run lifecycle, manifests, serialization, API/UI behavior, security boundaries, external tools, or supported environments require review, updated decision records where appropriate, and mapped verification. This baseline was approved on 2026-10-11; approval does not imply that the current implementation conforms.