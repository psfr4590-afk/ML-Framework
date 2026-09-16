from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"


def load_pipeline_config():
    p = ROOT / "config" / "pipeline_config.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def load_groups():
    p = ROOT / "config" / "dataset_groups.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return raw.get("dataset_groups", [])


def load_profiles():
    p = ROOT / "config" / "dataset_profiles.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return raw.get("dataset_profiles", [])


def profile_by_id(did):
    return next((p for p in load_profiles() if int(p.get("dataset_id", -1)) == int(did)), None)


def group_by_id(gid):
    return next((g for g in load_groups() if g.get("id") == gid), None)
