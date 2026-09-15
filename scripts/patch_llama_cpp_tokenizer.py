#!/usr/bin/env python3
"""Apply the Model Lab tokenizer compatibility overlay to pinned llama.cpp.

The project trains a Hugging Face BPE tokenizer with ByteLevel pre-tokenization.
llama.cpp identifies BPE pre-tokenizers by hashing tokenizer output and keeps a
registry of known hashes. A freshly trained vocabulary necessarily produces a
new hash even when its pre-tokenization behavior is the standard GPT-2-style
ByteLevel behavior. This small, deterministic overlay registers the exact
Model Lab smoke-tokenizer hash as ``gpt-2``.

The overlay is intentionally applied to the checked-out third-party tree at
reconciliation time instead of modifying the vendored upstream source in the
repository. It fails closed if the expected llama.cpp generated function is
not present, so an upstream layout change cannot silently receive a bad patch.
"""
from __future__ import annotations

import argparse
from pathlib import Path

MODEL_LAB_BPE_HASH = "e12d7d7d597f008d0cb30279fdbf0cb50824295d46ebda2bbea01ef7c2e8d97d"
MARKER = "# Marker: Start get_vocab_base_pre"
REGISTRATION = f'''        if chkhsh == "{MODEL_LAB_BPE_HASH}":\n            # Model Lab uses tokenizers.ByteLevel(add_prefix_space=False).\n            # Its freshly trained vocabulary produces a unique hash, but the\n            # pre-tokenization behavior is the standard GPT-2 ByteLevel form.\n            res = "gpt-2"\n'''


def patch_tokenizer_registry(llamacpp_dir: str | Path) -> bool:
    """Register the Model Lab BPE hash in a pinned llama.cpp checkout.

    Returns True when the file was changed and False when the registration was
    already present. Raises on an unexpected upstream source layout.
    """
    path = Path(llamacpp_dir).resolve() / "conversion" / "base.py"
    if not path.is_file():
        raise FileNotFoundError(f"llama.cpp converter source not found: {path}")

    text = path.read_text(encoding="utf-8")
    if MODEL_LAB_BPE_HASH in text:
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
    parser = argparse.ArgumentParser(description="Apply Model Lab's pinned llama.cpp tokenizer compatibility overlay")
    parser.add_argument("--llamacpp-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    changed = patch_tokenizer_registry(args.llamacpp_dir)
    print("Model Lab llama.cpp tokenizer overlay applied" if changed else "Model Lab llama.cpp tokenizer overlay already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
