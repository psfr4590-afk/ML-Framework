# Static Pipeline Release Audit

This document records what can be established from the repository without claiming a production crawl or long training run.

## 1. Repository and runtime contract

- Project-root discovery is independent of the caller's working directory.
- Python support is defined by `pyproject.toml` as `>=3.11,<3.15`.
- The bootstrapper has explicit PyTorch channel selection.
- Native llama.cpp is separately bootstrapped and pinned.
- Runtime datasets, checkpoints, GGUF artifacts, caches, logs, and live credentials are outside the source-tree contract.

## 2. Dependency and security gates

- `bootstrap.py --doctor` checks installation and host prerequisites.
- Runtime dependencies are declared in `pyproject.toml` and requirements files.
- The security gate checks tracked source, dependency consistency, and dependency vulnerabilities.

## 3. Configuration and dataset catalog

The checked-in dataset catalog contains ten groups:

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

## 4. Source provenance

Source manifests use schema 2 and retain dataset-group identity, source-definition hashes, source kind and identifier, revision/license fields, timestamps, and raw-source hashes when available.

A stale or incomplete source manifest cannot satisfy the production artifact lineage contract.

## 5. Stage lineage

The current stage contract is:

`crawl → clean → semantic dedup → weight → tokenize → shard → train → export`

Material artifacts are protected by hashes and stage provenance. Resume logic validates those records before reusing persisted output.

Shard manifests independently record shard sizes and SHA-256 values. Tokenizer and weighted-corpus artifacts are checked before export.

## 6. Training lineage

Training checkpoints retain model/training configuration identities, optimizer/scaler state, deterministic RNG and loader state, shard identity, source-manifest identity, and seed.

Production training refuses accidental CPU pretraining unless CPU training is explicitly allowed by configuration.

## 7. Export lineage

Export validates the checkpoint and the retained tokenizer, weighted-corpus, shard, source-manifest, and configuration identities before conversion.

The release path produces GGUF artifacts, export metadata, dataset/model cards, and hashes. Native verification additionally validates GGUF integrity and native inference.

## 8. Native release verification

`scripts/verify_release.py --bootstrap-native` is the repository's native release gate. It performs the static verification first, then reconciles the pinned llama.cpp dependency and executes the local deterministic fixture through tokenization, sharding, training, GGUF export, artifact verification, and native inference.

## 9. Runtime-only evidence

Static inspection cannot prove:

- availability or content of remote sources
- runtime HTTP responses or quotas
- legal rights for every external source
- actual production training loss, convergence, or model capability
- successful native verification on the intended deployment hardware

Those remain explicit runtime/operational gates.