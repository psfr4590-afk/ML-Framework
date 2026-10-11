# Governance package import blocker

The supplied source archive is named `ML-Framework-governance-package-v1.1.0-repository-mapped.zip` and contains a `v11/` directory. The full source package has not been imported to this repository path.

## Direct CI evidence

The Governance validation workflow ran against this branch and failed at **Require complete v1.1.0 package**. The checksum and Python validator steps were skipped because the normative files were absent. This is the expected fail-closed behavior, not a successful governance validation.

## Why this note exists

The GitHub connector currently available for this task supports creating UTF-8 text files and individual commits, but does not expose a binary ZIP upload or bulk multi-file import operation. The repository's CI cannot read a ZIP that exists only as a conversation attachment. Adding more copies of requirements or hand-recreating the catalog would lose source integrity and could silently corrupt historical checksums.

## Safe completion procedure

1. Extract the supplied ZIP locally.
2. Copy the complete `v11/` directory into this repository at `governance/v11/`, preserving every file and the `history/` subtree.
3. Check the source archive's checksums before modifying anything.
4. Verify `SHA256SUMS.txt` and the historical manifest according to their documented relative paths.
5. Commit the exact imported package on this branch.
6. Re-run this PR's CI and inspect every reported requirement/test gap.
7. Do not mark compliance complete until functional tests and the repository's own release verification pass on a pinned candidate commit.

## Status

This note is not normative and is not part of the supplied source package. It must not be treated as satisfying any requirement in that package.
