# Dataset provenance and source policy

Model Lab can technically collect and transform data, but the software cannot grant permission to use someone else's content for training. Operators are responsible for confirming that every source used by a run is lawful and appropriate for the intended dataset and model.

## What the pipeline records

Every stage writes an integrity manifest. The manifest chain ties an artifact to its input hash, pipeline configuration hash, stage, and stage-specific configuration or source metadata. This is intended to prevent an artifact produced from one corpus/configuration from being silently reused as if it came from another.

For a production dataset, retain a source manifest containing at least:

- source URL or dataset/repository identifier
- retrieval timestamp
- source type
- source revision/version when available
- applicable license or usage terms
- attribution requirements
- any operator approval or restriction notes
- raw-source artifact SHA-256
- the Git commit and pipeline configuration used to process it

## Licensing and terms

The seeded configuration is an engineering starting point, not a blanket license grant. Before a large or redistributed training run, review the terms for each configured web site, GitHub repository, arXiv source, Hugging Face dataset, search result, or other provider.

Do not assume that a public URL means unrestricted training rights. In particular, review dataset licenses, repository licenses, website terms, robots/publishing policies, attribution requirements, and any restrictions on redistribution or commercial use.

If the required rights or provenance cannot be established, exclude the source from the production run rather than relying on the crawler to make a legal determination.

## Removal and takedown

A production dataset should be rebuildable from source manifests. When a source must be removed, disable it in the source configuration, record the reason in the dataset provenance record, rebuild affected downstream artifacts, and preserve the resulting artifact hashes. Do not patch a generated training corpus in place without regenerating its provenance chain.

## Data quality

Provenance is separate from quality. A legally usable source can still be poor training data. Production runs should retain counts for acquisition, cleaning, deduplication, weighting, tokenization, and sharding, along with rejection reasons where available. Large changes in these counts should be reviewed before training.

## Boundary of responsibility

Model Lab provides technical controls for bounded acquisition, parsing, filtering, deduplication, weighting, and artifact integrity. It does not certify copyright ownership, licensing, consent, or legal compliance for a dataset. Those decisions remain with the operator or organization running the pipeline.
