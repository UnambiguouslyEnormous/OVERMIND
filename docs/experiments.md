# Experiments and evidence

OVERMIND evaluates exact-label text classification with explicit train/validation/test splits. This guide describes the implemented methods, promotion policy, and measured results. For controls and commands, use the [user guide](user-guide.md).

## Methods

| Method | What changes | Saved artifact |
| --- | --- | --- |
| CPU classifier weight training | Hashed-feature linear softmax weights trained by SGD | Reloadable weights and epoch cursor |
| LLM prompt optimization | System prompt supplied to an existing served model | Prompt configuration; base model weights unchanged |
| LLM retrieval augmentation | Prompt plus 1–4 examples selected by lexical scoring from the licensed training split | Prompt/reference corpus; base model weights unchanged |

The built-in curriculum controller is deterministic: it oversamples training errors and uses a bounded learning-rate schedule. A local or authorized cloud LLM mentor can instead select the CPU student's SGD learning rate, revising it every six epochs. For an LLM student, the mentor receives bounded hardware/model metadata, objective, balanced training examples, validation scores/failures, budget information, and the current run's candidate history. It chooses validated prompt/retrieval operations and receives their measured validation outcomes. Held-out inputs and answers never enter mentor requests.

Each LLM candidate has `candidate-N.json` and `validation-N.json`; `mentor-N.json` stores the validated command and rationale. Candidate history persists in SQLite. After the candidate limit, the best validation artifact is frozen for paired final testing. Ollama model digests, when exposed, are checked after baseline, before candidates, and around final verification; a changed digest cancels comparison. Other engines may not expose immutable identity, so keep the served model fixed.

## What the measurements mean

The included project-authored synthetic CC0 benchmark has 80 training, 24 validation, and 40 held-out examples across account, billing, security, and technical support. For the built-in SGD experiment, the baseline is an untrained classifier, so it is deliberately weak. The Qwen experiment instead compares a generic classification prompt with the selected prompt on the same fixed served model. This demonstrates real learning and artifact verification, not state-of-the-art performance or general language-model improvement.

The model uses deterministic hashed word, bigram, and character features with a softmax output. SGD minimizes cross-entropy. Extra practice is selected from training errors only. Each epoch's validation score controls checkpoint selection; the mentor can inspect validation outcomes. **Only after selection finishes** does the evaluator compare the original and frozen candidate on the final test split.

Promotion requires all of:

- Strict improvement in held-out exact-label accuracy.
- An exact, one-sided paired sign test with p ≤ 0.05.
- No per-label held-out accuracy regression.

Raw outputs, per-label results, the exact policy, dataset hash, candidate hash, and method name are stored. Failure, no gain, or insufficient evidence leaves the candidate available for inspection but creates no promotion artifact. Promotion records an approved artifact within that experiment; it does not replace any installed model or globally deploy a candidate.

The test set is held out from optimization within each experiment. It is **not cryptographically hidden from the user or a malicious local model server**. Repeated use of the same benchmark is exploratory and weakens fresh confirmation. Use newly authored independent tests for consequential decisions. Exact duplicate inputs are rejected across all splits; semantic near-duplicates are not automatically detected. Model-name changes at a running inference endpoint can invalidate a comparison; keep the served model fixed throughout a run.

## Verified results

These are measured runs on the project-authored CC0 benchmark, not fixture outputs. Original private artifacts remain in the local laboratory; public JSON summaries exclude raw prompts, credentials, configuration, database contents, and machine-specific paths. Saved candidate and dataset hashes were checked against their reports during beta preparation without rerunning paid inference.

### Qwen prompt optimization

| Measurement | Result |
| --- | --- |
| Mentor / student | OpenAI GPT-4.1 / Ollama `qwen2.5:1.5b` |
| Method | Prompt optimization; no student weight updates |
| Train / validation / held-out | 80 / 24 / 40 examples |
| Held-out baseline → candidate | **33/40 (82.5%) → 39/40 (97.5%)** |
| Gain | 15 percentage points |
| Selected validation score | 24/24 |
| Paired wins / losses | 7 / 1 |
| Exact one-sided paired p | 0.03515625 |
| Per-label regressions | None |
| Promotion | Passed the implemented policy |

The [sanitized Qwen summary](../examples/qwen-prompt-result.json) contains the full per-label measurements and policy. The [Laboratory screenshot](screenshots/laboratory-completed.png) and privacy-redacted [Evidence screenshot](screenshots/evidence-artifacts.png) show this completed experiment. It demonstrates one prompt improvement on one small routing benchmark and one setup, not general intelligence or broad model improvement. Reusing the test set is exploratory, not fresh confirmation. No live Anthropic or retrieval improvement is claimed.

Dataset SHA-256:
`f12cd7d7199688c6e359c6830029b4283769c8bd841a4fcd2eda845d75464805`

Candidate SHA-256:
`d43e1815b1a7ceca0bc1f43c200d4d24017de6a4f7cf2798cf7a20c21f24ad91`

### CPU classifier weight training

Recorded on 2026-10-15 using `./run.sh run`; private saved run `828cbca0f90a`.

| Measurement | Result |
| --- | --- |
| Method | Actual CPU softmax SGD weight training |
| Starting student | Zero-initialized, untrained text classifier |
| Train / validation / test | 80 / 24 / 40 original project-authored synthetic examples |
| Epochs | 18 |
| Selected validation accuracy | 95.83% |
| Held-out baseline accuracy | 25% (10/40) |
| Held-out candidate accuracy | 92.5% (37/40) |
| Paired wins / losses | 27 / 0 |
| Exact one-sided paired p | 7.450580596923828e-09 |
| Per-label regressions | None |
| Promotion | Passed the implemented evidence policy |

The baseline is deliberately weak. The result shows learning on this task, not general language-model improvement. Earlier development and clean-source smoke runs reproduced the same deterministic weights and 10/40 → 37/40 result; those repeats are reproducibility checks, not independent statistical confirmation. The [sanitized classifier summary](../examples/classifier-result.json) preserves the report fields; weights, dataset snapshot, paired predictions, and report remain private local artifacts.

Dataset SHA-256:
`f12cd7d7199688c6e359c6830029b4283769c8bd841a4fcd2eda845d75464805`

Candidate SHA-256:
`f1278fcd02217b7ee4b0a278364c0da44886ccb1ebdbeb56ba3eb9b69f45a6f9`

## Capability status

| Status | Capability |
| --- | --- |
| Exercised with real CPU training | SGD, saved-weight reuse, baseline/final evaluation, artifact hashes, promotion gating, checkpoint recovery, worker lifecycle, CLI |
| Exercised live on one setup | GPT-4.1 mentor → Qwen2.5 1.5B prompt optimization described above |
| Fixture coverage; broader live verification pending | Anthropic, local/compatible mentors, LLM-directed SGD, lexical retrieval, saved prompt/retrieval inference, additional provider/model combinations |
| Real screenshots available; full interactive acceptance pending | GTK configuration, Laboratory, Evidence & artifacts; pause/resume/stop and reopening still need the desktop checklist |
| Unimplemented | Generative-model LoRA/QLoRA/SFT, semantic/vector RAG, automatic continual/multi-task/general-intelligence training, dataset discovery, permitted synthetic-data generation, custom evaluators, model-server checkpoint export |

Saved classifier weights can be reused manually; experiment history is not continual learning. Retrieval is lexical, not vector search. A free-text objective does not create a new architecture or arbitrary benchmark. No GPU training or LoRA job is claimed. Ollama GGUF inference artifacts are not assumed to be trainable Transformer checkpoints. A future generative-weight backend would need compatible original weights, verified licenses, resource preflight, and preservation of the base model; it is not part of this beta.

## Verification scope

The recorded full suite includes actual CPU training and subprocess worker checks with Linux memory/time bounds. Provider protocols and cloud orchestration use explicitly labeled fixtures: metadata discovery/pagination, native schemas, candidate feedback, frozen evaluation, no-gain rejection, authorization, cost accounting, redaction, model identity checks, and training-only retrieval. Fixture outcomes are not model gains.

Development hardware observations were approximately 15.5 GiB RAM and 16 logical CPUs, with no working NVIDIA driver in that restricted session. They are not minimum requirements or certification of other hardware; the supplied screenshots reflect their own capture environment. No fresh OS install or complete interactive desktop acceptance is certified. See [beta readiness](beta-release.md) for the latest recorded checks and remaining work.
