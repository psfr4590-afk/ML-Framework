# Model Lab Release Readiness

This document is the current production-readiness contract for `main`. It distinguishes repository readiness from evidence that can only be produced by executing the release gate.

## Current RC gate state

| Area | Current state | Evidence |
|---|---|---|
| Repository hardening | Complete for current merged work | `main`, PRs #22 and #24 merged |
| Linux CI definition | Present | `.github/workflows/ci.yml` |
| Windows CI definition | Present | `.github/workflows/ci.yml` |
| PowerShell contract | Present | `.github/workflows/ci.yml` |
| Dependency consistency | Gated | `pip check` in CI/security/release |
| Dependency vulnerability scan | Gated | `scripts/security_gate.py` |
| Secret scan | Gated | `scripts/security_gate.py` |
| Python compile | Gated | CI + `scripts/verify_release.py` |
| Ruff F lint | Gated | CI + `scripts/verify_release.py` |
| Automated test coverage | Gated, >=75% | `pytest-cov` gate in `pyproject.toml` |
| Source provenance | Implemented | schema-2 source manifests |
| Artifact source/config/code identity | Implemented | stage provenance contracts |
| Network-dependent release smoke | Removed | native release smoke uses local fixture |
| GGUF integrity | Gated | `scripts/verify_gguf.py` |
| Native llama.cpp inference | Required for RC/release | `scripts/verify_release.py --bootstrap-native` |
| Release dependency evidence | Implemented | freeze + SBOM |
| Current main CI result | **PASS** | Linux + Windows CI green on latest verified main commit |
| Termux native quantizer execution | **Verified tool-level evidence** | Android 16/aarch64; pinned llama.cpp `b95502b...`; `llama-quantize --help` executed successfully on 2026-09-29 |
| Current native release result | **Pending execution** | complete `verify_release.py --bootstrap-native` and end-to-end export/inference remain required |
| Target-hardware validation | **Pending execution** | must be executed on intended deployment hardware |
| Production training/convergence | **Operational evidence** | separate from RC smoke |

## Release commands

Static verification:

```text
python scripts/verify_release.py
```

Full native RC/release verification:

```text
python scripts/verify_release.py --bootstrap-native
```

The native gate is intentionally separate from ordinary CI because it requires the pinned llama.cpp toolchain and a target environment. A green CI run is necessary but is not sufficient for a native production release.

## Evidence retained by the release gate

- Python compile result
- Ruff result including `ui/`
- pytest result and coverage JSON
- `pip check` result
- security gate result
- resolved dependency freeze
- SBOM
- source manifest and source-definition hashes
- export manifest
- dataset and model cards
- GGUF SHA-256 validation
- llama.cpp inference result

The 2026-09-29 Termux evidence proves the native quantizer can be built and
executed on Android 16/aarch64. It does not satisfy the full native release gate:
the Termux Python environment used for that check was outside the repository's
declared Python 3.11-3.13 support range and did not provide the required
`faiss-cpu>=1.15.0,<2` dependency. Therefore the native tool evidence and the
complete Model Lab release gate remain intentionally separate.

## Release boundary

A release is approved only when every required automated gate is green and the native verification has passed on the intended target environment.

Missing evidence is a release-process failure, not an implicit pass.

Historical reports remain historical records and must not be presented as current release evidence.
