# Model Lab Release Readiness

This document defines the release-readiness contract. It is intentionally status-neutral: current workflow results and release evidence must be checked for the exact commit being approved.

## Source and automated gates

| Area | Contract | Authoritative source |
|---|---|---|
| Python support | >=3.11,<3.15 | `pyproject.toml` |
| Linux CI | Python 3.11 and 3.14 | `.github/workflows/ci.yml` |
| Windows CI | Python 3.11 and 3.14 | `.github/workflows/ci.yml` |
| PowerShell contract | Required | `.github/workflows/ci.yml` |
| Dependency consistency | Required | `pip check` in CI/security/release |
| Vulnerability scan | Required | `scripts/security_gate.py` |
| Secret scan | Required | `scripts/security_gate.py` |
| Python compilation | Required | CI and `scripts/verify_release.py` |
| Ruff | Required | CI and `scripts/verify_release.py` |
| Pytest coverage | **90% aggregate minimum** | `[tool.coverage.report].fail_under` in `pyproject.toml` |
| Artifact/provenance integrity | Required | `pipeline/integrity.py` and stage contracts |
| Native llama.cpp verification | Required for native release | `scripts/verify_release.py --bootstrap-native` |
| Release evidence | Required | `scripts/generate_release_evidence.py` and release workflow |

## Verification commands

Static verification:

```text
python scripts/verify_release.py
```

Full native verification:

```text
python scripts/verify_release.py --bootstrap-native
```

The static command does not claim native conversion or inference. The native command adds the pinned llama.cpp bootstrap and the deterministic local export/inference fixture.

## Evidence retained

The release gate is expected to retain, where applicable:

- compilation and lint results
- pytest result and coverage JSON
- dependency consistency and security results
- dependency freeze and SBOM
- source and artifact manifests
- export manifest
- dataset and model cards
- GGUF hashes
- native inference result
- target-host information when target validation is required

## Environment boundary

Generic CI can validate source contracts, Python behavior, artifact logic, and the automated test suite. CUDA availability, native toolchain behavior, desktop/Tk behavior, and target deployment hardware remain environment-dependent.

Tool-level evidence, such as the historical Termux llama-quantize check, must not be presented as a complete native release result.

## Release boundary

A production release requires current evidence for the exact approved source commit. Missing evidence is a release-process failure, not an implicit pass.

Historical reports remain historical records and must not be used as current release status.