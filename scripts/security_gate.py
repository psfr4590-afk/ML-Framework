#!/usr/bin/env python3
"""Offline-friendly release security checks for tracked source and dependencies."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*[\"'][^\"']{12,}[\"']"),
)
SKIP_SUFFIXES = {".pyc", ".pyo", ".bin", ".pt", ".gguf", ".safetensors", ".png", ".jpg", ".jpeg", ".zip"}


def _tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError("git ls-files failed")
    return [ROOT / raw for raw in proc.stdout.decode("utf-8", errors="replace").split("\0") if raw]


def _secret_scan() -> list[str]:
    findings: list[str] = []
    for path in _tracked_files():
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                findings.append(f"{path.relative_to(ROOT)}:{number}")
    return findings


def main() -> int:
    failures: list[str] = []
    secret_findings = _secret_scan()
    if secret_findings:
        print("Potential tracked secrets detected:")
        for finding in secret_findings:
            print(f"  {finding}")
        failures.append("secret-scan")
    else:
        print("Secret scan: PASS")

    pip_check = subprocess.run([sys.executable, "-m", "pip", "check"], cwd=ROOT, check=False)
    if pip_check.returncode:
        failures.append("pip-check")
    else:
        print("pip check: PASS")

    try:
        import pip_audit  # noqa: F401
    except ImportError:
        print("pip-audit is not installed; refusing to mark dependency audit green")
        failures.append("pip-audit-missing")
    else:
        audit = subprocess.run([sys.executable, "-m", "pip_audit", "--strict"], cwd=ROOT, check=False)
        if audit.returncode:
            failures.append("pip-audit")
        else:
            print("pip-audit: PASS")

    if failures:
        print("SECURITY GATE FAILED:", ", ".join(failures))
        return 2
    print("SECURITY GATE PASSED: tracked-secret scan, dependency consistency, and vulnerability audit are green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
