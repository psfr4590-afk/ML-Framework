# Model Lab Verification

Verification has three distinct layers:

1. **Automated repository checks**: compilation, lint, pytest/coverage, configuration, artifact integrity, and security.
2. **Target-environment checks**: CUDA, native llama.cpp, required executables, host readiness, and deployment hardware.
3. **Human-visible checks**: desktop launch, display fit, navigation, controls, and observable UI behavior.

## Automated

Run:

```bash
python -m pytest -q
python scripts/verify_release.py
```

The repository enforces a **90% aggregate pytest coverage threshold**.

## Target environment

For a native release, run:

```bash
python scripts/verify_release.py --bootstrap-native
```

For target-hardware evidence, the release workflow uses:

```bash
python scripts/verify_target_hardware.py
```

These commands produce evidence only when they are actually executed.

## Human-visible desktop

Use the target Windows environment to verify launch, display fit, navigation, pipeline controls, credential handling, stop behavior, and the relevant Command Center surfaces.

Do not convert an unexecuted desktop check into PASS.

Current status belongs to GitHub Actions and retained release evidence, not to this static page.