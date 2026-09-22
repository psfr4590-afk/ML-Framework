from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import re
import tomllib

import pytest
import yaml

from pipeline.integrity import artifact_valid, write_manifest
from pipeline.orchestrator import Pipeline

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SEMANTIC_PACKAGES = {"sentence-transformers", "faiss-cpu"}

# Primary/maintained sources selected for subject-matter seeding. This is intentionally
# explicit: "high quality" should be an enforceable repository contract, not a vibe.
APPROVED_HOSTS = {
    "docs.python.org", "doc.rust-lang.org", "developer.mozilla.org", "docs.kernel.org",
    "postgresql.org", "www.postgresql.org", "sqlite.org", "kubernetes.io", "www.rfc-editor.org",
    "git-scm.com", "go.dev", "pytorch.org", "scikit-learn.org", "jax.readthedocs.io",
    "huggingface.co", "mlflow.org", "airflow.apache.org", "owasp.org", "csrc.nist.gov",
    "www.cisa.gov", "lean-lang.org", "coq.inria.fr", "www.nist.gov", "www.swgde.org",
    "plato.stanford.edu", "www.nature.com", "www.acm.org", "www.cs.cmu.edu", "www.cs.cornell.edu",
    "www.sec.gov", "fred.stlouisfed.org", "www.bis.org", "www.ncbi.nlm.nih.gov", "www.ebi.ac.uk",
    "docs.ros.org", "www.genome.gov", "www.annualreviews.org", "openstax.org", "dlmf.nist.gov",
    "mathworld.wolfram.com", "ocw.mit.edu", "www.siam.org", "docs.scipy.org", "numpy.org",
    "www.statsmodels.org", "www.ams.org", "www.mit.edu", "www.aps.org", "www.aip.org",
    "materialsproject.org", "www.cern.ch", "pubs.acs.org", "www.osti.gov", "pubmed.ncbi.nlm.nih.gov",
    "www.nih.gov", "www.cdc.gov", "www.fda.gov", "www.who.int", "www.niehs.nih.gov",
    "www.niaid.nih.gov", "www.law.cornell.edu", "www.justice.gov", "www.ftc.gov", "www.govinfo.gov",
    "www.congress.gov", "eur-lex.europa.eu", "www.oecd.org", "aclanthology.org", "www.nltk.org",
    "spacy.io", "www.elastic.co", "www.ling.upenn.edu", "www.cl.cam.ac.uk", "www.isca-archive.org",
    "climate.nasa.gov", "www.noaa.gov", "www.usgs.gov", "www.epa.gov", "www.energy.gov",
    "www.eia.gov", "www.ipcc.ch", "www.copernicus.eu", "earthdata.nasa.gov", "docs.docker.com",
}


def _load(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_semantic_dedup_dependencies_are_required_everywhere():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_deps = {re.split(r"[<>=!~ ]", dep, maxsplit=1)[0] for dep in metadata["project"]["dependencies"]}
    requirements = {
        re.split(r"[<>=!~ ]", line, maxsplit=1)[0]
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and not line.startswith("-")
    }
    assert REQUIRED_SEMANTIC_PACKAGES <= project_deps
    assert REQUIRED_SEMANTIC_PACKAGES <= requirements


def test_semantic_dedup_is_not_documented_as_optional():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start_here = (ROOT / "docs/development/START_HERE.md").read_text(encoding="utf-8")
    for doc in (readme, start_here):
        assert "requirements-optional.txt" not in doc
        assert not re.search(r"sentence-transformers.*optional", doc, re.IGNORECASE)
        assert not re.search(r"FAISS.*optional", doc, re.IGNORECASE)


def test_every_canonical_dataset_group_has_meaningful_high_quality_web_seeds():
    data = _load("config/dataset_groups.yaml")
    groups = data["dataset_groups"]
    assert len(groups) == 10
    for group in groups:
        urls = group["web"]["seed_urls"]
        assert len(urls) >= 10, group["id"]
        assert len(urls) == len(set(urls)), group["id"]
        for url in urls:
            parsed = urlparse(url)
            assert parsed.scheme == "https", url
            assert parsed.hostname in APPROVED_HOSTS, url


def test_general_seed_file_is_primary_source_oriented():
    urls = [
        line.strip()
        for line in (ROOT / "config/seed_urls.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(urls) >= 40
    assert len(urls) == len(set(urls))
    assert all(urlparse(url).scheme == "https" for url in urls)
    assert sum(urlparse(url).hostname in APPROVED_HOSTS for url in urls) >= 35


def test_canonical_ui_and_docs_advertise_all_seeded_dataset_groups():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dataset_ui = (ROOT / "ui/screens/dataset.py").read_text(encoding="utf-8")
    assert "Ten dataset groups are preconfigured" in readme
    assert "Dataset 001–010 are seeded" in dataset_ui


def test_starter_requires_semantic_dedup_and_uses_local_model_by_default():
    cfg = _load("config/pipeline_config.yaml")
    assert cfg["stages"]["semantic_dedup"] is True
    assert cfg["embed_dedup"]["mode"] == "auto"
    assert cfg["embed_dedup"]["allow_model_download"] is False


def test_resume_skip_requires_exact_artifact_provenance(tmp_path):
    artifact = tmp_path / "artifact.jsonl"
    artifact.write_text('{"text":"stable"}\n', encoding="utf-8")
    provenance = {"schema": 2, "input_sha256": "a" * 64, "config_sha256": "b" * 64}
    write_manifest(artifact, kind="clean", provenance=provenance)

    pipeline = Pipeline.__new__(Pipeline)
    pipeline._resume = True
    assert pipeline._should_skip(artifact, "clean", provenance)
    changed = dict(provenance)
    changed["config_sha256"] = "c" * 64
    assert not pipeline._should_skip(artifact, "clean", changed)


def test_resume_skip_rejects_byte_corruption(tmp_path):
    artifact = tmp_path / "artifact.jsonl"
    artifact.write_text('{"text":"stable"}\n', encoding="utf-8")
    write_manifest(artifact, kind="clean", provenance={"schema": 2})
    assert artifact_valid(artifact)
    artifact.write_text('{"text":"tampered"}\n', encoding="utf-8")
    assert not pipeline_artifact_is_valid(artifact)


def pipeline_artifact_is_valid(path: Path) -> bool:
    return artifact_valid(path)


def test_orchestrator_source_keeps_global_dedup_streaming_contract():
    source = (ROOT / "pipeline/orchestrator.py").read_text(encoding="utf-8")
    assert "yield from deduper.stream(unique_docs(), buffer_size=buffer_size)" in source


def test_release_verifier_contains_network_free_export_and_inference_gate():
    source = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert "network-free" in source
    assert "scripts/verify_gguf.py" in source
    assert "inference_validation" in source


def test_no_stale_optional_dependency_file_is_referenced():
    for path in (ROOT / "README.md", ROOT / "docs/development/START_HERE.md"):
        text = path.read_text(encoding="utf-8")
        assert "requirements-optional.txt" not in text


def test_doctor_treats_semantic_dedup_dependencies_as_required():
    from pipeline.doctor import _semantic_dedup_state
    ok, detail = _semantic_dedup_state()
    assert ok, detail


def test_semantic_dedup_required_dependencies_are_not_hidden_behind_optional_extras():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "sentence-transformers>=6.0.1" in pyproject
    assert "faiss-cpu>=1.15.0" in pyproject
    assert "sentence-transformers>=6.0.1" in requirements
    assert "faiss-cpu>=1.15.0" in requirements


def test_semantic_dedup_auto_mode_fails_if_required_package_is_missing(monkeypatch):
    import pipeline.embedder.semantic_dedup as module
    monkeypatch.setattr(module, "ST_AVAILABLE", False)
    monkeypatch.setattr(module, "FAISS_AVAILABLE", True)
    deduper = module.SemanticDeduplicator({"mode": "auto"})
    from pipeline.types import Document
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        deduper.run([Document(doc_id="1", text="test")])
