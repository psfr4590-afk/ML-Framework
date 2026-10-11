# Machine Verification Runbook

## Purpose
Run repository checks on the target machine without real credentials or an accidental full training workload.

## Before running
1. Check out the exact branch and record `git rev-parse HEAD`.
2. Use a clean working tree and disposable test dataset.
3. Use synthetic credentials only. Never include `.env`, tokens, private datasets, or model weights in evidence.
4. Record OS, architecture, Python version, and optional dependencies such as `psutil`, `torch`, and `tkinter`.

## PowerShell evidence capture
```powershell
$ErrorActionPreference = "Continue"
$Evidence = Join-Path $env:TEMP ("ml-framework-evidence-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $Evidence | Out-Null
git rev-parse HEAD | Tee-Object "$Evidence\commit.txt"
git status --short | Tee-Object "$Evidence\git-status.txt"
python --version 2>&1 | Tee-Object "$Evidence\python.txt"
python -c "import platform; print(platform.platform()); print(platform.machine())" 2>&1 | Tee-Object "$Evidence\platform.txt"
python -m pip freeze 2>&1 | Out-File "$Evidence\pip-freeze.txt"
python -m pytest -q tests/governance/test_requirement_acceptance.py tests/governance/test_operational_failure_modes.py 2>&1 | Tee-Object "$Evidence\governance-tests.txt"
$GovernanceExit = $LASTEXITCODE
python -m pytest -q 2>&1 | Tee-Object "$Evidence\full-suite.txt"
$FullSuiteExit = $LASTEXITCODE
"acceptance_exit=$GovernanceExit`nfull_suite_exit=$FullSuiteExit" | Out-File "$Evidence\exit-codes.txt"
```
Use the repository-managed environment if the project prescribes one. Record dependency-install failures separately from test failures.

## Required operational checks
- **Process tree:** use a harmless fixture that spawns a parent and child. Request cancellation and verify both exit within the timeout. Never use a real training job as the first test.
- **Startup race:** repeatedly cancel during process startup; verify no worker survives and final state is terminal.
- **Restart recovery:** abruptly stop and restart the Command Center on a disposable run. Dead workers should become ERROR/failed; unrelated live processes must not be adopted or killed.
- **PID reuse:** test mismatched process creation times. If identity support is unavailable, record the conservative-recovery limitation.
- **Redaction:** synthetic secrets only. Test raw, JSON-escaped, Base64, URL-encoded, exception, multiline, event, and subprocess-output paths. Scan logs for synthetic values and encodings without including real credentials.
- **Release gate:** from a clean clone, test missing RC flags and forced test failures. Each must produce a nonzero exit code and no success report.
- **Clean clone:** follow documented bootstrap instructions in a new directory and preserve command output and exit status.

## Evidence to return
Provide a zip of the evidence directory and include exact commit SHA, clean/dirty status, OS/Python/toolchain details, commands and exit codes, pass/fail/skip counts, full stack traces, whether failures reproduce on the base commit, parent/child PID observations, redaction scan results, and release-gate report/status.

## Interpretation
Do not run destructive cleanup or release commands against production data. A green governance module alone does not establish readiness; the full regression suite and operational scenarios must be reviewed.