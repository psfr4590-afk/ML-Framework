# Model Lab Production Release Checklist

A release is not considered trusted merely because unit tests are green. Every item below is an evidence gate.

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
- [ ] llama.cpp can load the final GGUF and generate at least one token
- [ ] Interrupted stage resumes only from verified artifacts
- [ ] Changed source/config invalidates the affected artifact rather than silently reusing it
