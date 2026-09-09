from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_declares_supported_python_and_cli():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]

    assert project["name"] == "model-lab-framework"
    assert project["version"] == "1.3.0"
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"]["mlab"] == "run_pipeline:main"


def test_packaging_dependencies_match_runtime_contract():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    declared = set(metadata["project"]["dependencies"])

    for line in requirements.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert line in declared

    assert all(not dependency.lower().startswith("torch") for dependency in declared)


def test_torch_has_a_separate_host_specific_requirement():
    torch_requirements = (ROOT / "requirements-torch.txt").read_text(encoding="utf-8")
    assert "torch>=2.5,<3" in torch_requirements
