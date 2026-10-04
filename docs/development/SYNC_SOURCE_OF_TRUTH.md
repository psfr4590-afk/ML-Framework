# Source of Truth

The repository's source of truth is the Git history and code on the branch/commit being reviewed. Once a change is merged, `main` is the authoritative public branch.

When documentation, tests, release notes, or historical reports disagree with the code, inspect the current code and workflow configuration first and update the stale document.

Historical archives, delivery notes, generated reports, and working-session snapshots are not authoritative source.

Runtime datasets, checkpoints, caches, build outputs, live credentials, and separately bootstrapped native dependencies are outside the source-tree contract unless explicitly tracked by the repository.

## Status claims

Documentation must not hard-code a workflow result, test count, coverage result, release approval, or target-machine result unless that evidence is explicitly tied to a commit and retained as current release evidence.

Current status belongs to GitHub Actions and the release evidence produced for the approved commit.