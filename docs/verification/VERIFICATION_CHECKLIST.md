# Model Lab Verification Checklist

Use this checklist to distinguish automated evidence from checks that require a real target environment or human observation.

## Automated

- Package/build metadata and project-root discovery
- Canonical pipeline stage and CLI contracts
- Dataset identity and configuration contracts
- Artifact integrity and provenance contracts
- Backend startup behavior
- Command-center localhost and mutation-boundary security
- Credential encryption/decryption paths
- Secret and dependency security checks
- Python compilation and Ruff
- Full pytest suite and enforced 90% aggregate coverage gate
- Release documentation and structural checks

## Target machine

- Required Python/runtime dependencies
- NVIDIA/PyTorch CUDA observability when applicable
- Native llama.cpp checkout and export tools
- Pipeline doctor and Command Center health
- Target hardware characteristics required for deployment
- Native GGUF conversion, quantization, and inference when the full native gate is required

## Human-visible desktop checks

- Desktop launch and display fit
- Navigation surfaces
- Dataset selection and pipeline controls
- Stop behavior
- Credential save/replace behavior
- Sources, Crawler, Training, Outputs, Logs, System, Configuration, Diagnostics, and Command Center surfaces

## Release rule

Do not convert an unexecuted target-machine or human-visible check into PASS. Record PASS, FAIL, or UNKNOWN with the environment and evidence reference.

The desktop 1760×990 value is a UI verification target, not an automated correctness requirement.
