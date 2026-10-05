# Model Lab UI

The optional Windows/Tk application is a desktop control surface for the existing localhost command center. It does not contain a second implementation of the training pipeline.

Canonical launch from the Model Lab root:

```powershell
python .\launch.py
```

The desktop surface delegates backend actions to the FastAPI command center and exposes navigable screens for dataset selection, pipeline controls, outputs, logs, configuration, diagnostics, and system state.

Target display: **1760×990**.

This display size is a verification target for the desktop presentation, not a runtime or model-training requirement.
