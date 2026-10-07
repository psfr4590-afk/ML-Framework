# Model Lab: start here

This guide is the operational walkthrough for a new checkout. It intentionally focuses on getting the system running, not on the project's development history.

## 1. Clone

```bash
git clone https://github.com/psfr4590-afk/ML-Framework.git
cd ML-Framework
```

## 2. Install

Windows PowerShell:

```powershell
python .\bootstrap.py --install
```

Linux / macOS / Termux:

```bash
python3 bootstrap.py --install
```

The bootstrapper installs the declared dependencies and selects the CPU or CUDA PyTorch wheel automatically from detected NVIDIA hardware.

## 3. Preflight

```text
Windows: python .\bootstrap.py --doctor
Other:   python3 bootstrap.py --doctor
```

Resolve any required `FAIL` result before continuing. A missing llama.cpp checkout is expected until native export is requested.

## 4. Prove the pipeline

```text
Windows: python .\mlframework.py smoke
Other:   python3 mlframework.py smoke
```

This runs the bounded starter configuration through the real pipeline. It is a functional check, not a production training run.

Check the result:

```text
mlframework status
mlframework runs
```

If you did not install the editable package, use the equivalent Python entry points:

```text
python run_pipeline.py --doctor
python run_pipeline.py --list-stages
python run_pipeline.py --list-groups
```

## 5. Launch the UI

Windows desktop:

```powershell
python .\launch.py
```

Browser command center:

```powershell
python .\run_command_center.py
```

The desktop launcher starts the UI and its localhost backend. The browser launcher starts only the local FastAPI command center.

## 6. Continue into a real run

Inspect hardware first:

```text
Windows: python .\run_pipeline.py --doctor --hardware-report
Other:   python3 run_pipeline.py --doctor --hardware-report
```

Then choose an appropriate configuration under `config/`. The starter profile is intentionally bounded and should not be mistaken for a useful production model.

The main CLI workflow is:

```text
doctor → smoke → dataset → train → evaluate → export → infer
```

## 7. Native export

Export requires the pinned llama.cpp toolchain:

```bash
python scripts/verify_release.py --bootstrap-native
```

Or, for the normal CLI path after a trained checkpoint exists:

```text
mlframework export
mlframework infer
```

## 8. Engineering verification

Static verification:

```bash
python scripts/verify_release.py
```

Full RC verification:

```bash
python scripts/verify_release.py --bootstrap-native --ui-probe --clean-clone
```

See the [architecture guide](../architecture/ARCHITECTURE.md) for system design and the [release checklist](../release/RELEASE_CHECKLIST.md) for release-specific requirements.
