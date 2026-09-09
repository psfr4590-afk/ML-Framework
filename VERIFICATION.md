# Model Lab Verification

Model Lab verification is divided into automated contract tests, Python compilation, target-machine environment checks, and human-visible desktop smoke checks.

Run `python -m pytest -q` for the automated suite. On the target Windows machine, also run `python -m pytest -q .\tests\model_lab\test_machine_environment.py`.

The release procedure is documented in `VERIFICATION_CHECKLIST.md` and `scripts/run_release_verification.ps1`.