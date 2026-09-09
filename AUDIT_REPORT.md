# Model Lab Production Audit

Release approval requires automated tests, the non-destructive environment doctor, a native llama.cpp bootstrap, and a reduced end-to-end training/export smoke test on the target machine. The project does not claim operations that were not actually executed.

Mandatory gates: compileall, pytest, doctor, native bootstrap, reduced corpus run, checkpoint reload, GGUF conversion, quantization when requested, manifest hash verification, and llama.cpp inference smoke test.
