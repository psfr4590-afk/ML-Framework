# Static Pipeline Release Audit

This document records what can be established from the repository without claiming a production crawl or long training run.

## 1. Repository and runtime contract

- Project-root discovery is independent of the caller's working directory.
- Python support is defined by `pyproject.toml` and `bootstrap.py` as `>=3.11,<3.15`.
- The bootstrapper has explicit PyTorch channel selection and hardware detection.
- Native llama.cpp is separately bootstrapped and pinned.
- Runtime datasets, checkpoints, GGUF artifacts, caches, logs, and live credentials are outside the source-tree contract.

## 2. Canonical architecture

- `pipeline/orchestrator.py` is the single production stage orchestrator.
- `pipeline.types.Document` is the canonical preprocessing document contract.
- `pipeline/app.py` is a compatibility surface and does not define a second pipeline.
- The command center delegates stage execution to `run_pipeline.py`.
- The optional Tk UI delegates backend work to the localhost command center.

The stage contract is:

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

## 3. Dependency and security gates

- `bootstrap.py --doctor` checks installation and host prerequisites.
- `run_pipeline.py --doctor` checks project/runtime readiness.
- Runtime dependencies are declared in `pyproject.toml` and requirements files.
- The security gate checks tracked source, dependency consistency, and dependency vulnerabilities.
- Command-center ingestion is confined to its imports root and rejects traversal, absolute paths, and symlink sources.

## 4. Configuration and dataset catalog

The checked-in canonical dataset catalog contains ten groups:

1. `swe_cs_systems`
2. `ai_ml_cybersec_dataeng`
3. `sci_reasoning_forensics_formal`
4. `domain_finance_bio_robotics`
5. `math_statistics_optimization`
6. `physics_chemistry_materials`
7. `biomedical_health_science`
8. `law_compliance_governance`
9. `linguistics_information_retrieval`
10. `climate_energy_geospatial`

Configuration validation and dataset-group identity are enforced by the current configuration/schema code.

## 5. Source provenance

Source manifests use schema 2 and retain dataset-group identity, source-definition hashes, source kind and identifier, revision/license fields, timestamps, and raw-source hashes when available.

A stale or incomplete source manifest cannot satisfy the production artifact lineage contract.

## 6. Stage lineage

Each material stage output carries integrity/provenance information. Resume logic validates those records before reusing persisted output.

- crawl produces source/provenance state
- clean normalizes and filters
- semantic dedup removes near-duplicates using the configured embedding/index path
- weight applies source/content weighting
- tokenize produces the BPE tokenizer and manifest
- shard produces binary shards and a shard manifest with sizes/hashes
- train produces integrity-protected checkpoints with deterministic state
- export validates upstream identities before creating HF/GGUF/Ollama artifacts

## 7. Training architecture

The built-in model is a Llama-style decoder-only transformer with RMSNorm, RoPE, causal attention/grouped-query support, SwiGLU, tied embeddings, and configurable geometry.

Available presets are approximately 85M, 117M, and 360M parameters. Hardware-aware profile selection can reduce context, batch geometry, and training steps for constrained hosts.

Production training refuses accidental CPU pretraining when `allow_cpu_training=false`.

## 8. Export lineage

Export validates the checkpoint and retained tokenizer, weighted-corpus, shard, source-manifest, configuration, and model-vocabulary identities before conversion.

The release path produces GGUF artifacts, export metadata, dataset/model cards, and hashes. Native verification additionally validates GGUF integrity and native inference.

## 9. Native release verification

`scripts/verify_release.py --bootstrap-native` is the repository's native release gate. It performs the static verification first, reconciles the pinned llama.cpp dependency, creates the deterministic local fixture, runs the enabled tokenization/sharding/training/export path, verifies the resulting GGUF, and exercises native inference.

## 10. Runtime-only evidence

Static inspection cannot prove:

- availability or content of remote sources
- runtime HTTP responses or quotas
- legal rights for every external source
- actual production training loss, convergence, or model capability
- successful native verification on the intended deployment hardware
- human-visible desktop behavior

Those remain explicit runtime/operational gates.
