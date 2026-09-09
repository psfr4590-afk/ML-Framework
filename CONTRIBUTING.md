# Contributing

ML-Framework is intentionally structured around a small number of canonical pipeline stages. Contributions should improve the existing architecture rather than introduce parallel implementations of the same behavior.

## Development principles

1. Keep pipeline behavior deterministic and resumable where practical.
2. Preserve artifact integrity checks and atomic writes.
3. Keep credentials and generated training artifacts out of source control.
4. Prefer contract tests for stage boundaries and integration tests for cross-stage behavior.
5. Do not silently turn a failed hardware or dependency check into a pass.

## Validation

Run the non-destructive readiness check and the test suite before submitting changes:

```powershell
python .\run_pipeline.py --doctor
python -m pytest -q
python .\scripts\verify_release.py
```

Target-machine checks should be run on the hardware that will actually execute training or export.
