#!/usr/bin/env python3
"""Apply the Model Lab tokenizer compatibility overlay to pinned llama.cpp.

Model Lab trains a Hugging Face BPE tokenizer with the tokenizers library's
ByteLevel pre-tokenizer. llama.cpp's converter historically identifies BPE
pre-tokenizers through a hash registry. A newly trained vocabulary produces a
new hash even when the pre-tokenization behavior is unchanged, so a
hash-specific registration would break every newly trained model.

The overlay therefore adds a structural check: when the Hugging Face backend
reports the standard ByteLevel pre-tokenizer, llama.cpp should emit its
existing GPT-2-compatible pre-tokenizer implementation. The patch is applied
to the checked-out third-party tree at reconciliation time instead of
modifying vendored upstream source in the repository.

The patch fails closed if the expected generated function is absent, so an
upstream converter layout change cannot silently receive a bad modification.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MARKER = "# Marker: Start get_vocab_base_pre"
REGISTRATION = '''        backend_tokenizer = getattr(tokenizer, "backend_tokenizer", None)\n        pre_tokenizer = getattr(backend_tokenizer, "pre_tokenizer", None)\n        if pre_tokenizer is not None and pre_tokenizer.__class__.__name__ == "ByteLevel":\n            # Model Lab uses tokenizers.ByteLevel(add_prefix_space=False).\n            # Map the standard ByteLevel behavior to llama.cpp's GPT-2\n            # pre-tokenizer implementation without relying on a vocab hash.\n            res = "gpt-2"\n'''


def patch_tokenizer_registry(llamacpp_dir: str | Path) -> bool:
    """Register standard ByteLevel BPE behavior in a llama.cpp checkout.

    Returns True when the file was changed and False when the compatibility
    overlay was already present. Raises on an unexpected upstream source
    layout.
    """
    path = Path(llamacpp_dir).resolve() / "conversion" / "base.py"
    if not path.is_file():
        raise FileNotFoundError(f"llama.cpp converter source not found: {path}")

    text = path.read_text(encoding="utf-8")
    if "Model Lab uses tokenizers.ByteLevel(add_prefix_space=False)." in text:
        return False
    if MARKER not in text:
        raise RuntimeError(
            "Unsupported llama.cpp converter source: generated get_vocab_base_pre marker is missing"
        )

    marker_index = text.index(MARKER)
    res_index = text.find("        res = None", marker_index)
    if res_index < 0:
        raise RuntimeError(
            "Unsupported llama.cpp converter source: get_vocab_base_pre initialization was not found"
        )
    insert_at = res_index + len("        res = None\n")
    updated = text[:insert_at] + REGISTRATION + text[insert_at:]
    path.write_text(updated, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Model Lab's llama.cpp tokenizer compatibility overlay")
    parser.add_argument("--llamacpp-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    changed = patch_tokenizer_registry(args.llamacpp_dir)
    print("Model Lab llama.cpp tokenizer overlay applied" if changed else "Model Lab llama.cpp tokenizer overlay already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
