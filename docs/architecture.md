# Architecture

The native GTK application is a control client. It creates licensed dataset snapshots and launches an independent Python worker. The same worker runs from the CLI. No ML runtime is needed for the implemented CPU student.

```text
GTK desktop / CLI
        │
        ├── SQLite experimental memory + decisions
        ├── Atomic JSON datasets, weights, prompt artifacts, predictions, reports
        │
        └── bounded worker (exclusive flock; memory cap; hard time alarm)
                inspect → baseline validation → improve → freeze → verify → done
                    │                           │                │
                    ├── CPU softmax student     │                └── exact-match evaluator
                    └── local provider API      └── validation-only selection
                           ↑
                    mentor schema validation
```

`data.py` validates explicit splits, labels, sizes, license declarations, and exact input disjointness. `model.py` implements real feature hashing, softmax inference, cross-entropy and SGD. `providers.py` is the inference-engine boundary, shared by mentor and student roles. `lab.py` is the bounded experiment controller, including curriculum selection, mentor delegation, evaluation, final verification, and process lifecycle. `store.py` provides SQLite memory and atomic, fsynced artifact writes. `desktop.py` is the native interface; it never trains on the GTK event thread.

The external mentor receives only scoped operational tools represented by validated JSON commands: select a learning rate for real CPU SGD, or select prompt optimization/retrieval augmentation and the bounded configuration for real local student inference. The controller executes these tools within fixed limits. Malformed output fails visibly; it never falls back to an invented successful result. LLM planning calls, explanations, epoch losses, validation outcomes, and final decisions persist. Local mentor context includes previous validation summaries, objectives, plans, and statuses, not final test contents or scores. Cloud mentors receive only current-run history, scoped to the explicit data-sharing grant.

The built-in mentor is deliberately a transparent algorithm. It provides a genuine no-download training path without impersonating a powerful LLM. Its curriculum oversamples current training mistakes; its learning-rate schedule uses fixed bounded choices. It does not reason about arbitrary objectives.

The evaluator is independent of the mentor's judgment: it computes exact objective label matches using supplied answers, not an LLM's self-rating. Train/validation/test data remain separate in the controller. Test progress is persisted only after selection is frozen, and recovery resumes verification instead of returning to optimization. A local malicious engine is outside this isolation boundary: this is a single-user application, not a hostile-code security sandbox.

New inference engines implement `inspect` and `generate` without changing the role model. Additional improvement backends should expose capability and hardware preflight, a typed bounded plan, artifact identity, baseline restoration, recovery cursors, and a standardized evaluation contract. A future generative-weight backend must distinguish base weights and adapters from prompt artifacts. The new `cloud.py` official-provider transport requires a per-request reservation. `store.py` maintains an additive SQLite `cloud_calls` ledger with atomic cost reservation and token reconciliation. `security.py` holds session credentials, filters worker environments and redacts persistence. Cloud configuration requires an explicit spending/data-sharing grant, positive budget/rates, and output ceilings before dispatch. Provider training-use rights must be recorded before enabling synthetic-data tools.

Persistence is recoverable rather than a distributed transaction: an epoch's weights and cursor are atomic, and SQLite tracks phases and budgets. An interrupted operation may repeat; each dispatched inference consumes its reservation before the request. A report is finalized from the frozen model and paired predictions. Reports identify small-benchmark and repeated-test limitations. There is no global auto-deployment or overwriting of an original model.

References consulted for future compatibility: [Ollama generation API](https://docs.ollama.com/api/generate), [Ollama model inspection API](https://github.com/ollama/ollama/blob/main/docs/api.md#show-model-information), [Hugging Face PEFT LoRA](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora), and [PEFT quantization](https://huggingface.co/docs/peft/main/developer_guides/quantization). LoRA is research context here, not an implemented backend.

Phase 2 configuration, authorization boundaries and verification limitations are documented in [the Phase 2 guide](phase2.md). `retrieval.py` retrieves only licensed training examples, and `inference.py` runs saved prompt/retrieval artifacts through the local-only transport.
