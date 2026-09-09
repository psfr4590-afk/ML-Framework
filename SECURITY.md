# Security Policy

## Scope

ML-Framework is a local-first model-data and training framework. Security issues involving credential handling, command execution, filesystem boundaries, network access, dataset ingestion, or artifact integrity are in scope.

## Reporting

Please do not publish sensitive details in a public issue when the report could expose credentials, private data, or an exploitable execution path. Contact the repository owner privately through GitHub with reproduction details and the affected commit.

Never include API keys, access tokens, passwords, private dataset contents, or other secrets in a report.

## Design expectations

- Secrets belong in environment variables or local credential storage, never in committed configuration.
- Generated datasets and model artifacts should remain outside source control.
- Network-facing crawlers should preserve configured timeouts, retries, politeness controls, and allow/block lists.
- Artifact manifests and SHA-256 checks are part of the trust boundary and should not be bypassed silently.
