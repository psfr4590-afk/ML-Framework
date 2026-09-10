# Model Lab Production Release Checklist

A release is not considered trusted merely because unit tests are green. Every item below is an evidence gate.

## Automated and environment gates

- [ ] `python -m compileall -q .`
- [ ] `python -m pytest -q`
- [ ] `python run_pipeline.py --doctor` has no required failures
- [ ] Pinned llama.cpp bootstrap completed and commit is `b95502b...`
- [ ] `convert_hf_to_gguf.py` exists in the pinned checkout
- [ ] `llama-quantize` exists when quantized export is enabled
- [ ] Small real corpus successfully produces clean/deduped/weighted JSONL
- [ ] Tokenizer vocabulary exactly matches `train.vocab_size`
- [ ] Train/validation shards pass manifest hash verification
- [ ] Reduced training run writes a checkpoint and its integrity manifest
- [ ] Checkpoint can be reloaded successfully
- [ ] GGUF F16 export succeeds
- [ ] Requested quantized GGUF export succeeds
- [ ] Export manifest hashes match the files on disk
- [ ] Dataset and model cards are generated for every export
- [ ] Export manifest records dataset/model card paths and SHA-256 hashes
- [ ] llama.cpp can load the final GGUF and generate at least one token
- [ ] Interrupted stage resumes only from verified artifacts
- [ ] Changed source/config invalidates the affected artifact rather than silently reusing it

## Dataset and security gates

- [ ] Every production source has a retained source manifest with URL/identifier, retrieval time, revision, license/usage terms, and raw-source SHA-256
- [ ] Attribution and redistribution requirements have been reviewed before publishing a dataset or model
- [ ] Sources without established training rights are excluded
- [ ] Removal/takedown changes are applied by rebuilding the affected artifact chain, not by editing generated corpora in place
- [ ] Crawler boundary tests cover loopback, private/link-local/multicast IPv4 and IPv6, encoded IP forms, and redirects to non-public destinations
- [ ] Untrusted document/archive parsing is bounded by size and extraction limits and avoids unsafe deserialization
- [ ] Credential storage has been checked for secret redaction and appropriate local file/OS protections
- [ ] Command-center endpoints have been reviewed for localhost binding and unauthorized remote access
- [ ] Dependency vulnerability/license scanning has been completed for the release environment
- [ ] A software bill of materials is retained for distributed builds when required by the deployment context

## Reproducibility and artifact lineage

- [ ] Full Git commit SHA is recorded
- [ ] Pipeline configuration SHA-256 is recorded
- [ ] Dependency lock/constraints fingerprint is recorded when a locked environment is used
- [ ] Seed/source manifest SHA-256 is recorded
- [ ] Shard manifest SHA-256 is recorded
- [ ] Model configuration and random seeds are recorded
- [ ] Hardware and driver information is recorded for training runs
- [ ] Deterministic-mode settings are recorded when deterministic output is promised
- [ ] Final GGUF SHA-256 is recorded

Each completed gate should include its execution environment, result, and relevant artifact or log evidence. Current automated CI status is separate from target-machine native verification.
