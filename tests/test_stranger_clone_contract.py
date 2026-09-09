from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_PUBLIC_FILES = {
    "README.md",
    "START_HERE.md",
    "LICENSE",
    ".gitignore",
    "pyproject.toml",
    "requirements.txt",
    "requirements-torch.txt",
    "bootstrap.py",
    "run_pipeline.py",
    "launch.py",
    "run_command_center.py",
    "scripts/verify_release.py",
}

FORBIDDEN_PUBLIC_PATH_PARTS = {
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    "datasets",
    "output",
    "scratch",
    "checkpoints",
    "models",
}


def _tracked_paths() -> set[str]:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_public_tree_contains_canonical_entrypoints() -> None:
    tracked = _tracked_paths()
    missing = sorted(REQUIRED_PUBLIC_FILES - tracked)
    assert not missing, f"Missing canonical public files: {missing}"


def test_public_tree_contains_no_generated_or_local_runtime_paths() -> None:
    tracked = _tracked_paths()
    violations = sorted(
        path
        for path in tracked
        if any(part in FORBIDDEN_PUBLIC_PATH_PARTS for part in Path(path).parts)
        or path.endswith((".log", ".tmp", ".ckpt", ".pt", ".pth", ".gguf"))
    )
    assert not violations, f"Generated/local artifacts are tracked publicly: {violations[:20]}"


def test_canonical_first_run_commands_are_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start_here = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{start_here}"
    required_fragments = [
        "python bootstrap.py --install",
        "python bootstrap.py --doctor",
        "python run_pipeline.py --no-resume",
        "config/pipeline_config.yaml",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in combined]
    assert not missing, f"Canonical first-run documentation is incomplete: {missing}"


def test_no_large_local_vendor_checkout_is_tracked() -> None:
    tracked = _tracked_paths()
    vendor_paths = [path for path in tracked if path.startswith("third_party/llama.cpp/")]
    assert not vendor_paths, "llama.cpp source should remain a separately bootstrapped dependency"


@pytest.mark.parametrize(
    "command",
    [
        "python bootstrap.py --install",
        "python bootstrap.py --doctor",
        "python run_pipeline.py --list-stages",
        "python run_pipeline.py --list-groups",
        "python run_pipeline.py --doctor",
        "python run_pipeline.py --no-resume",
    ],
)
def test_documented_commands_reference_existing_entrypoints(command: str) -> None:
    entrypoint = command.split()[1]
    assert (ROOT / entrypoint).is_file(), f"Documented entrypoint does not exist: {entrypoint}"
