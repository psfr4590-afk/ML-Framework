# Model Lab

**Model Lab** is the package name for the **M²S Model Training Pipeline** command center.

The desktop application is a local control surface over the existing localhost FastAPI command center and pretraining pipeline. It does not implement a second copy of the pipeline.

## Launch

```powershell
pip install -r .\requirements.txt
python .\launch.py
```

The desktop UI is designed for a 1760×990 display.

## Pipeline

Crawl → Clean → Semantic Dedup → Weight → Tokenize → Shard → Train → Export.

## Seeded datasets

Four dataset groups are preconfigured under `config/dataset_groups.yaml`: `swe_cs_systems`, `ai_ml_cybersec_dataeng`, `sci_reasoning_forensics_formal`, and `domain_finance_bio_robotics`. `config/seed_urls.txt` provides the initial web crawl seeds.

## Credentials

GitHub (`GITHUB_TOKEN`), Hugging Face (`HF_TOKEN`), Google API key (`GOOGLE_API_KEY`), and Google Search engine ID (`GOOGLE_CX`) are supported. Secrets stay out of version control.

## Verify

```powershell
python .\run_pipeline.py --doctor
python -m pytest -q
python .\scripts\verify_release.py
```

Final GGUF export requires the pinned llama.cpp toolchain and its conversion/quantization binaries. Native build and target-machine validation are explicit release gates, not assumed successes.

Generated datasets, checkpoints, caches, model artifacts, native build products, and secrets are intentionally excluded from version control.