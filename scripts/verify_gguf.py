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


def _read_gguf_metadata(path: Path) -> dict[str, Any]:
    """Read the scalar GGUF metadata needed for deployment verification.

    This deliberately implements only the GGUF header/metadata wire format so
    verification does not depend on an unpinned Python gguf package.
    """
    import struct

    TYPE_FORMATS = {
        0: ("B", 1), 1: ("b", 1), 2: ("H", 2), 3: ("h", 2),
        4: ("I", 4), 5: ("i", 4), 6: ("f", 4), 7: ("?", 1),
        10: ("Q", 8), 11: ("q", 8), 12: ("d", 8),
    }

    def read_string(handle) -> str:
        length = struct.unpack("<Q", handle.read(8))[0]
        raw = handle.read(length)
        if len(raw) != length:
            raise RuntimeError("truncated GGUF string")
        return raw.decode("utf-8")

    def read_value(handle, kind: int) -> Any:
        if kind == 8:
            return read_string(handle)
        if kind == 9:
            element_type = struct.unpack("<I", handle.read(4))[0]
            count = struct.unpack("<Q", handle.read(8))[0]
            return [read_value(handle, element_type) for _ in range(count)]
        fmt = TYPE_FORMATS.get(kind)
        if fmt is None:
            raise RuntimeError(f"unsupported GGUF metadata type: {kind}")
        value = struct.unpack("<" + fmt[0], handle.read(fmt[1]))
        return value[0]

    with path.open("rb") as handle:
        if handle.read(4) != b"GGUF":
            raise RuntimeError(f"invalid GGUF magic: {path}")
        version = struct.unpack("<I", handle.read(4))[0]
        if version not in (1, 2, 3):
            raise RuntimeError(f"unsupported GGUF version: {version}")
        tensor_count = struct.unpack("<Q", handle.read(8))[0]
        metadata_count = struct.unpack("<Q", handle.read(8))[0]
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key = read_string(handle)
            kind = struct.unpack("<I", handle.read(4))[0]
            metadata[key] = read_value(handle, kind)
    return {
        "version": version,
        "tensor_count": tensor_count,
        "metadata_count": metadata_count,
        "metadata": metadata,
    }


def _build_command(
    cli_path: Path,
    model_path: Path,
    prompt: str,
    context_length: int | None = None,
) -> list[str]:
    command = [
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
        "--check-tensors",
    ]
    if context_length is not None:
        command.extend(["-c", str(context_length)])
    if cli_path.name.lower() == "llama.exe":
        return [str(cli_path), "cli", *command[1:]]
    return command


def verify_gguf(
    model: str | Path,
    llama_cli: str | Path,
    prompt: str = "Hello",
    context_length: int | None = None,
    expected_special_tokens: dict[str, int] | None = None,
) -> dict[str, Any]:
    model_path = Path(model).resolve()
    cli_path = Path(llama_cli).resolve()

    if not model_path.is_file() or model_path.stat().st_size <= 0:
        raise FileNotFoundError(f"GGUF model is missing or empty: {model_path}")
    if not cli_path.is_file():
        raise FileNotFoundError(f"llama inference executable is missing: {cli_path}")

    metadata = _read_gguf_metadata(model_path)
    values = metadata["metadata"]
    architecture = values.get("general.architecture")
    if architecture not in (None, "llama"):
        raise RuntimeError(f"unexpected GGUF architecture: {architecture!r}")

    context_key = f"{architecture or 'llama'}.context_length"
    embedded_context = values.get(context_key)
    if context_length is not None and embedded_context is not None and int(embedded_context) != int(context_length):
        raise RuntimeError(
            f"GGUF context length mismatch: expected {context_length}, embedded {embedded_context}"
        )

    special_tokens = {
        "bos": values.get("tokenizer.ggml.bos_token_id"),
        "eos": values.get("tokenizer.ggml.eos_token_id"),
        "pad": values.get("tokenizer.ggml.padding_token_id"),
    }
    if expected_special_tokens:
        for name, expected in expected_special_tokens.items():
            actual = special_tokens.get(name)
            if actual is not None and int(actual) != int(expected):
                raise RuntimeError(f"GGUF special token mismatch for {name}: expected {expected}, embedded {actual}")

    cmd = _build_command(cli_path, model_path, prompt, context_length)
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=120)
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        detail = stderr[-2000:] if stderr else stdout[-2000:]
        raise RuntimeError(f"llama inference failed with exit code {proc.returncode}: {detail}")
    if not stdout:
        raise RuntimeError("llama.cpp loaded the GGUF but generated no visible token output")

    return {
        "status": "passed",
        "model": str(model_path),
        "llama_cli": str(cli_path),
        "command": cmd,
        "prompt": prompt,
        "generated_output": stdout,
        "checks": {
            "gguf_header": "passed",
            "model_loading": "passed",
            "tensor_validation": "passed",
            "architecture": architecture or "llama",
            "context_length": embedded_context if embedded_context is not None else context_length,
            "tokenizer": "embedded GGUF tokenizer metadata present" if any(k.startswith("tokenizer.ggml.") for k in values) else "not reported",
            "special_tokens": special_tokens,
            "special_token_validation": "passed" if expected_special_tokens else "recorded",
            "generation": "passed",
        },
        "metadata": {
            "version": metadata["version"],
            "tensor_count": metadata["tensor_count"],
            "metadata_count": metadata["metadata_count"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load and execute a GGUF with llama.cpp")
    parser.add_argument("--model", required=True)
    parser.add_argument("--llama-cli", required=False)
    parser.add_argument("--llamacpp-dir", required=False)
    parser.add_argument("--manifest")
    parser.add_argument("--prompt", default="Hello")
    parser.add_argument("--context-length", type=int)
    parser.add_argument("--bos-token-id", type=int)
    parser.add_argument("--eos-token-id", type=int)
    parser.add_argument("--pad-token-id", type=int)
    args = parser.parse_args(argv)

    if bool(args.llama_cli) == bool(args.llamacpp_dir):
        parser.error("provide exactly one of --llama-cli or --llamacpp-dir")

    try:
        cli = Path(args.llama_cli).resolve() if args.llama_cli else _find_cli(Path(args.llamacpp_dir).resolve())
        expected = {
            name: value for name, value in (
                ("bos", args.bos_token_id), ("eos", args.eos_token_id), ("pad", args.pad_token_id)
            ) if value is not None
        }
        result = verify_gguf(args.model, cli, args.prompt, args.context_length, expected)
        if args.manifest:
            manifest_path = Path(args.manifest).resolve()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            manifest["inference_validation"] = result
            _atomic_json(manifest_path, manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"GGUF VERIFICATION FAILED: {exc}")
        return 2

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
