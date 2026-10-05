# Source of Truth

The repository's source of truth is the Git history and code on the branch/commit being reviewed. Once a change is merged, `main` is the authoritative public branch.

The current architecture is defined by the implementation under `pipeline/`, `command_center/`, `ui/`, `config/`, and the root entrypoints, with workflow configuration defining CI/release behavior.

When documentation, tests, release notes, or historical reports disagree with the code, inspect the current code and workflow configuration first and update the stale document.

Historical archives, delivery notes, generated reports, and working-session snapshots are not authoritative source.

Runtime datasets, checkpoints, caches, build outputs, live credentials, and separately bootstrapped native dependencies are outside the source-tree contract unless explicitly tracked by the repository.

## Status claims

Documentation must not hard-code a workflow result, test count, coverage result, release approval, or target-machine result unless that evidence is explicitly tied to a commit and retained as current release evidence.

Current status belongs to GitHub Actions and the release evidence produced for the approved commit.

## Architecture invariants

Documentation should preserve these source-level invariants:

- `pipeline/orchestrator.py` is the canonical stage orchestrator.
- `pipeline.types.Document` is the canonical preprocessing document contract.
- The command center delegates stage execution to `run_pipeline.py`.
- The desktop UI delegates backend work to the localhost command center.
- Dataset identity and artifact provenance must survive stage boundaries.
- Runtime artifacts and credentials are not source-controlled.
- Native llama.cpp is an external, pinned, reconciled dependency rather than vendored source.
