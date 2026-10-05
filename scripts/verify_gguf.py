#!/usr/bin/env python3
"""Verify that a GGUF artifact loads and generates output with llama.cpp."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _find_cli(llamacpp_dir: Path) -> Path:
    """Find a llama.cpp inference executable across supported build layouts."""
    names = (
        "llama.exe",
        "llama-cli.exe",
        "llama-cli",
    )

    bases = (
        llamacpp_dir / "build",
        llamacpp_dir / "build-model-lab",
        llamacpp_dir / "bin",
        llamacpp_dir,
    )

    for base in bases:
        if not base.is_dir():
            continue

        for name in names:
            matches = list(base.rglob(name))
            if matches:
                return matches[0]

    raise FileNotFoundError(
        f"llama inference executable not found under {llamacpp_dir}"
    )


def _build_command(
    cli_path: Path,
    model_path: Path,
    prompt: str,
) -> list[str]:
    """Build the inference command for legacy and dispatcher-style llama.cpp."""
    if cli_path.name.lower() == "llama.exe":
        return [
            str(cli_path),
            "cli",
            "-m",
            str(model_path),
            "-p",
            prompt,
            "-n",
            "1",
            "--single-turn",
            "--no-display-prompt",
            "--simple-io",
        ]

    return [
        str(cli_path),
        "-m",
        str(model_path),
        "-p",
        prompt,
        "-n",
        "1",
        "--single-turn",
        "--no-display-prompt",
        "--simple-io",
    ]


def verify_gguf(
    model: str | Path,
    llama_cli: str | Path,
    prompt: str = "Hello",
) -> dict[str, Any]:
    model_path = Path(model).resolve()
    cli_path = Path(llama_cli).resolve()

    if not model_path.is_file() or model_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"GGUF model is missing or empty: {model_path}"
        )

    if not cli_path.is_file():
        raise FileNotFoundError(
            f"llama inference executable is missing: {cli_path}"
        )

    cmd = _build_command(cli_path, model_path, prompt)

    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0:
        detail = stderr[-2000:] if stderr else stdout[-2000:]
        raise RuntimeError(
            f"llama inference failed with exit code "
            f"{proc.returncode}: {detail}"
        )

    if not stdout:
        raise RuntimeError(
            "llama.cpp loaded the GGUF but generated no visible token output"
        )

    return {
        "status": "passed",
        "model": str(model_path),
        "llama_cli": str(cli_path),
        "command": cmd,
        "prompt": prompt,
        "generated_output": stdout,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load a GGUF with llama.cpp and generate one token"
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--llama-cli", required=False)
    parser.add_argument("--llamacpp-dir", required=False)
    parser.add_argument("--manifest")
    parser.add_argument("--prompt", default="Hello")
    args = parser.parse_args(argv)

    if bool(args.llama_cli) == bool(args.llamacpp_dir):
        parser.error(
            "provide exactly one of --llama-cli or --llamacpp-dir"
        )

    try:
        cli = (
            Path(args.llama_cli).resolve()
            if args.llama_cli
            else _find_cli(Path(args.llamacpp_dir).resolve())
        )

        result = verify_gguf(args.model, cli, args.prompt)

        if args.manifest:
            manifest_path = Path(args.manifest).resolve()
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file()
                else {}
            )
            manifest["inference_validation"] = result
            _atomic_json(manifest_path, manifest)

        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    except Exception as exc:
        print(f"GGUF VERIFICATION FAILED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
