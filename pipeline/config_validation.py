"""Strict configuration validation with actionable errors."""
from __future__ import annotations

QUANTS = {"F16", "Q4_K_M", "Q5_K_M", "Q8_0"}
PRESETS = {"85M", "117M", "360M"}
STAGES = {"crawl", "clean", "semantic_dedup", "weight", "tokenize", "shard", "train", "export"}


def validate_config(cfg: dict) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("Pipeline configuration must be a YAML object")
    required = ("pipeline", "stages", "crawl", "clean", "embed_dedup", "weight", "tokenizer", "shard", "train", "export")
    for section in required:
        if not isinstance(cfg.get(section), dict):
            raise ValueError(f"Missing or invalid configuration section: {section}")
    stages = cfg["stages"]
    unknown_stages = set(stages) - STAGES
    if unknown_stages:
        raise ValueError(f"Unsupported pipeline stages: {', '.join(sorted(unknown_stages))}")
    invalid_stage_values = [name for name, enabled in stages.items() if not isinstance(enabled, bool)]
    if invalid_stage_values:
        raise ValueError(f"Pipeline stage flags must be boolean: {', '.join(sorted(invalid_stage_values))}")
    if "model_preset" in cfg["pipeline"]:
        raise ValueError("pipeline.model_preset is obsolete; configure train.model_preset instead")
    tok, shard, train, export = cfg["tokenizer"], cfg["shard"], cfg["train"], cfg["export"]
    vocab = int(tok.get("vocab_size", 0))
    seq = int(shard.get("sequence_length", 0))
    if vocab <= 0:
        raise ValueError("tokenizer.vocab_size must be > 0")
    if vocab > 65536 and str(shard.get("dtype", "uint16")) == "uint16":
        raise ValueError("tokenizer.vocab_size > 65536 requires shard.dtype=uint32")
    if seq <= 0:
        raise ValueError("shard.sequence_length must be > 0")
    shard_size = int(shard.get("shard_size_tokens", 0))
    if shard_size < seq + 1:
        raise ValueError("shard.shard_size_tokens must be at least sequence_length + 1")
    val = float(shard.get("val_fraction", 0.0))
    if not 0.0 < val < 1.0:
        raise ValueError("shard.val_fraction must be between 0 and 1")
    steps = int(train.get("total_steps", 0))
    if steps <= 0:
        raise ValueError("train.total_steps must be > 0")
    if int(train.get("batch_size", 0)) <= 0 or int(train.get("grad_accum_steps", 0)) <= 0:
        raise ValueError("train.batch_size and train.grad_accum_steps must be > 0")
    preset = str(train.get("model_preset", "85M"))
    if preset not in PRESETS:
        raise ValueError(f"train.model_preset '{preset}' is unsupported")
    auto_size = bool(train.get("auto_size", False))
    if auto_size and "model_preset" not in train:
        raise ValueError("train.model_preset must remain defined as the manual fallback when train.auto_size=true")
    if train.get("target_training_hours") is not None and float(train["target_training_hours"]) <= 0:
        raise ValueError("train.target_training_hours must be > 0 when configured")
    if train.get("observed_tokens_per_sec") is not None and float(train["observed_tokens_per_sec"]) <= 0:
        raise ValueError("train.observed_tokens_per_sec must be > 0 when configured")
    if int(train.get("warmup_steps", 0)) >= steps:
        raise ValueError("train.warmup_steps must be smaller than train.total_steps")
    quant = str(export.get("quant", "F16")).upper()
    if quant not in QUANTS:
        raise ValueError(f"export.quant '{quant}' is unsupported")
    if not str(export.get("llamacpp_dir", "")).strip():
        raise ValueError("export.llamacpp_dir must be configured")
