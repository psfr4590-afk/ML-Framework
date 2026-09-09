"""Non-destructive environment checks for Model Lab.

The doctor intentionally reports capabilities instead of pretending that optional
native/GPU components are required everywhere. It leaves no runtime artifacts.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path


def _check(name: str, ok: bool, detail: str, required: bool = True) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail, "required": bool(required)}


def _python_ok() -> bool:
    return sys.version_info >= (3, 11)


def _writable(path: Path) -> bool:
    path = path.resolve()
    if not path.exists() or not path.is_dir():
        return os.access(path.parent, os.W_OK)
    return os.access(path, os.W_OK)


def _torch_state() -> tuple[bool, str]:
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:
        return False, f"torch unavailable: {type(exc).__name__}: {exc}"
    cuda = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
    if not cuda:
        return True, f"torch {torch.__version__}; CUDA unavailable (CPU-only runtime)"
    try:
        count = torch.cuda.device_count()
        names = [torch.cuda.get_device_name(i) for i in range(count)]
        return True, f"torch {torch.__version__}; CUDA available; {count} GPU(s): {', '.join(names)}"
    except Exception as exc:
        return True, f"torch {torch.__version__}; CUDA reported available but device details failed: {exc}"


def _llamacpp_state(root: Path) -> tuple[bool, str]:
    target = root / "third_party" / "llama.cpp"
    converter = target / "convert_hf_to_gguf.py"
    if not target.is_dir():
        return False, "llama.cpp checkout not present"
    if not converter.is_file():
        return False, "llama.cpp checkout present but convert_hf_to_gguf.py is missing"
    quant = list(target.rglob("llama-quantize*"))
    if not quant:
        return False, "converter present; llama-quantize executable not found"
    return True, f"llama.cpp present; converter and quantizer found ({quant[0]})"


def run_doctor(root: str | Path) -> tuple[bool, list[dict]]:
    root = Path(root).resolve()
    checks: list[dict] = []
    checks.append(_check("project root", (root / "run_pipeline.py").is_file() and (root / "pipeline").is_dir(), str(root)))
    checks.append(_check("Python", _python_ok(), f"{sys.version.split()[0]} (requires >=3.11)"))
    checks.append(_check("pipeline config", (root / "config" / "pipeline_config.yaml").is_file(), "config/pipeline_config.yaml"))
    checks.append(_check("seed URLs", (root / "config" / "seed_urls.txt").is_file(), "config/seed_urls.txt"))

    try:
        importlib.import_module("pipeline.orchestrator")
        checks.append(_check("pipeline imports", True, "pipeline.orchestrator imported successfully"))
    except Exception as exc:
        checks.append(_check("pipeline imports", False, f"{type(exc).__name__}: {exc}"))

    torch_ok, torch_detail = _torch_state()
    checks.append(_check("PyTorch", torch_ok, torch_detail))
    llama_ok, llama_detail = _llamacpp_state(root)
    checks.append(_check("llama.cpp export tooling", llama_ok, llama_detail, required=False))

    output = root / "output"
    checks.append(_check("output writable", _writable(output), str(output)))
    checks.append(_check("git", shutil.which("git") is not None, "git executable on PATH", required=False))
    checks.append(_check("cmake", shutil.which("cmake") is not None, "cmake executable on PATH", required=False))
    checks.append(_check("Windows", os.name == "nt", f"os.name={os.name}", required=False))

    required_failed = any((not item["ok"]) and item["required"] for item in checks)
    return not required_failed, checks


__all__ = ["run_doctor"]
