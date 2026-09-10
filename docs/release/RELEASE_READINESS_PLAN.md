# Model Lab Release Readiness

This document is the current production-readiness contract for `main`. Historical plans remain in Git history; this file describes the current implementation and gates.

## Current gate state

| Area | Status | Evidence / gate |
|---|---|---|
| Linux CI | Required | `.github/workflows/ci.yml` |
| Windows CI | Required | `.github/workflows/ci.yml` |
| PowerShell contract | Required | `.github/workflows/ci.yml` |
| Dependency consistency | Required | `pip check` |
| Dependency vulnerability scan | Required | `scripts/security_gate.py` |
| Secret scan | Required | `scripts/security_gate.py` |
| Python compile | Required | CI + `scripts/verify_release.py` |
| Ruff F lint | Required | CI + `scripts/verify_release.py` |
| Automated test coverage | Required, >=75% | `pytest-cov` gate |
| UI static lint | Required | CI includes `ui/` |
| Source provenance | Required | generated `source_manifest.json` |
| Artifact source/config/code identity | Required | stage provenance schema 2 |
| Network-dependent release smoke | Removed | release smoke uses local fixture |
| GGUF integrity | Required | `scripts/verify_gguf.py` |
| Native llama.cpp inference | Required for release | `scripts/verify_release.py --bootstrap-native` |
| Release dependency evidence | Required | freeze + SBOM evidence |

## Production invariants

1. A production artifact must have a complete provenance chain. Unknown licensing or revision information is retained as `unknown` and is never silently inferred.
2. Artifact reuse must fail closed when source definitions, pipeline configuration, or stage implementation identity changes.
3. External source-definition files, including `config/seed_urls.txt`, participate in provenance identity.
4. Command-center API mutations require the local control header and reject cross-origin browser requests.
5. Credential storage may only populate the explicit provider environment-variable allowlist.
6. API clients receive stable error codes and safe messages, not raw implementation exceptions.
7. Configuration validation rejects unknown sections/keys and cross-section incompatibilities before execution.
8. CI must compile and lint the UI as well as the core pipeline.
9. CI must enforce the coverage threshold.
10. A release must include dependency-resolution evidence and an SBOM.
11. The final release gate must execute the native GGUF export and llama.cpp inference path on the actual target environment. CI alone does not satisfy that hardware-specific gate.

## Release commands

Static verification:

```text
python scripts/verify_release.py
```

Full native release verification:

```text
python scripts/verify_release.py --bootstrap-native
```

The native gate is intentionally separate from ordinary CI because it requires the pinned llama.cpp toolchain and a real target environment. A green CI run is necessary but not sufficient for a native production release.

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

## Release decision

A release is **GO** only when every required automated gate is green and the native verification has passed on the target hardware. Missing evidence is a failure of the release process, not an implicit pass.
