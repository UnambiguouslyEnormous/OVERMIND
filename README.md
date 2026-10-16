# OVERMIND

A native Linux AI apprenticeship laboratory with real, bounded experiments and evidence before promotion.

**Linux source-checkout beta.** It trains a small CPU text classifier from real examples, saves its weights, compares a frozen candidate against its original student on held-out examples, and records why promotion passed or failed. Local LLMs or OpenAI/Anthropic cloud mentors can direct bounded experiments through actual inference APIs. Cloud mentors require explicit authorization and a configured budget. See the [Phase 2 configuration guide](docs/phase2.md).

A completed live OpenAI GPT-4.1 → Ollama Qwen2.5 1.5B **prompt-optimization** experiment improved held-out support-routing accuracy from **33/40 (82.5%) to 39/40 (97.5%)**. This changed the system prompt, not Qwen's weights. The small benchmark does not establish general intelligence or broad model improvement. See the [sanitized result](examples/qwen-prompt-result.json) and [verification record](docs/phase2-verification.md).

The targeted [mentor response validation fix](docs/mentor-response-fix.md) documents structured proposals, bounded corrections, diagnostics, and safely rerunning a failed experiment.

Credential protections, private data permissions, and local/CI secret-check setup are documented in [security hardening](docs/security-hardening.md).

## Run

Use a Linux desktop with **system Python 3.12+**, Bash, and GTK 3/PyGObject. Ubuntu 24.04 or a compatible Pop!_OS installation is a suitable starting point; older system Pythons are unsupported. Install the small system dependencies with your distribution's package manager:

```bash
sudo apt install git python3 python3-gi gir1.2-gtk-3.0
python3 --version
# Replace REPOSITORY_URL with this repository's URL.
git clone REPOSITORY_URL OVERMIND
cd OVERMIND
./run.sh
```

For an already downloaded checkout, start at `cd OVERMIND`. `run.sh` locates its own checkout and also works from another working directory or a path containing spaces. It is the supported portable launcher; no machine-specific desktop shortcut is shipped. Run with system Python, which can see distro GTK bindings. No pip installation, model download, GPU, credentials, or network connection is required for the built-in classifier experiment. CLI-only use needs no GTK bindings. Binary packages and a first-run installer are not provided.

1. Keep **Curriculum controller** and **CPU text classifier** selected for the first run.
2. Use the included CC0 support-routing dataset, or choose a licensed dataset with explicit train/validation/test splits.
3. Set epochs, wall time, worker memory, and inference-call limits.
4. Click **RUN EXPERIMENT**. Read the decisions and measurements in Laboratory, and inspect the saved report and candidate in Evidence & artifacts.
5. Try the resulting classifier with your own text. Use **Use saved student weights** in a new experiment to start from an earlier classifier checkpoint.

The built-in controller is a **deterministic curriculum algorithm, not an LLM**. The built-in student is a **trainable linear neural text classifier, not a generative language model**. A free-text objective alone cannot turn it into a different model architecture or create an arbitrary benchmark. Supply a suitable dataset and labels for a different classification task.

Persistent experiments live in `lab-data/`; use `./run.sh --data /your/path` to select a new/empty dedicated directory or an existing recognized OVERMIND laboratory. Unrelated nonempty directories, home/source roots, symlinks and hardlinks are rejected before permission migration. Back up existing data before upgrading. Closing the application stops its active worker and preserves completed checkpoints; pause/resume works while the application is open. Recover applies to unexpected worker exits.

## Headless use

```bash
./run.sh hardware
./run.sh run
./run.sh run --epochs 8
./run.sh example-dataset /tmp/my-dataset.json
./run.sh run --dataset /tmp/my-dataset.json
./run.sh list
./run.sh show EXPERIMENT_ID
./run.sh recover INTERRUPTED_EXPERIMENT_ID
./run.sh predict lab-data/EXPERIMENT_ID/candidate.json 'Please refund the duplicate charge'
python3 -m unittest discover -s tests -v
```

`--data` is a global option and comes before the command. CLI runs are foreground processes; desktop controls apply to the worker launched by that desktop instance. Do not launch multiple desktop instances against one data directory. A process lock prevents concurrent training workers. SIGTERM/emergency stop ends the worker; an unexpected exit is marked interrupted when the desktop next opens or polls.

## Connect actual local models

Ollama and local OpenAI-compatible engines are supported through the same provider interface; neither role is tied to a cloud company. Start and provision your inference engine separately. OVERMIND never silently downloads models or installs a service.

- Select **Ollama** and enter `http://127.0.0.1:11434` plus the exact installed model name. **Inspect connection** queries real model metadata, including architecture, quantization, capability, and license fields when the engine exposes them.
- Select **Compatible API** for a local engine exposing `/v1/models` and `/v1/chat/completions`. Enter its root URL, such as `http://127.0.0.1:8080`, without `/v1`. Architecture inspection is limited to what the endpoint actually exposes.
- For an LLM mentor with the CPU student, the mentor sees hardware, architecture, training examples, validation outcomes, and past validation summaries. It returns a bounded SGD learning rate and explanation. The worker executes actual training. The mentor can revise its recommendation every six epochs.
- For an LLM student, select a local or authorized cloud LLM mentor. The mentor chooses prompt optimization or retrieval augmentation across a configurable bounded candidate count; real student inference is scored on validation examples. The best prompt is frozen and compared with the original generic classification prompt on the held-out split. Its artifact records **prompt optimization** or **retrieval augmentation**, with no claim of weight training.
- The same local model can fill both roles. Use separately named model versions in your engine if you need distinct LLM checkpoints. Saved OVERMIND classifier checkpoints can directly become subsequent students.

Enable the explicit local dataset-sharing checkbox before dispatching text to an inference server through the desktop. CLI use of a provider configuration explicitly selects that dispatch. The test prompts are sent only to the student during final verification; answers and test cases are never included in mentor requests. A local server may itself be configured to proxy elsewhere: you are responsible for its deployment. Use engines that truly run locally.

Example configuration for an Ollama mentor and real classifier training:

```json
{
  "objective": "Improve routing of support tickets using the licensed dataset",
  "mentor": {"kind": "ollama", "url": "http://127.0.0.1:11434", "model": "YOUR_INSTALLED_MODEL"},
  "student": {"kind": "linear"},
  "epochs": 18,
  "minutes": 15,
  "memory_mb": 512,
  "max_calls": 240
}
```

Save it as `config.json`, then run `./run.sh run --config config.json`. An LLM student uses the same provider object as the mentor. A classifier checkpoint uses `{"kind":"linear","checkpoint":"/absolute/path/candidate.json"}`. The snapshot is copied before training and never overwritten.

**OpenAI and Anthropic cloud mentors are now implemented**, with session/environment credentials, authenticated model discovery, explicit paid-use and cloud-sharing authorization, pre-dispatch cost reservations and usage tracking. Local inference transports remain loopback-only; cloud transport uses fixed official HTTPS hosts. No paid calls are made by default. See the [Phase 2 guide](docs/phase2.md) for setup, pricing assumptions, permission boundaries and unverified integrations.

## What the measurements mean

The included project-authored synthetic CC0 benchmark has 80 training, 24 validation, and 40 held-out examples across account, billing, security, and technical support. For the built-in SGD experiment, the baseline is an untrained classifier, so it is deliberately weak. The Qwen experiment instead compares a generic classification prompt with the selected prompt on the same fixed served model. This demonstrates real learning and artifact verification, not state-of-the-art performance or general language-model improvement.

The model uses deterministic hashed word, bigram, and character features with a softmax output. SGD minimizes cross-entropy. Extra practice is selected from training errors only. Each epoch's validation score controls checkpoint selection; the mentor can inspect validation outcomes. **Only after selection finishes** does the evaluator compare the original and frozen candidate on the final test split.

Promotion requires all of:

- Strict improvement in held-out exact-label accuracy.
- An exact, one-sided paired sign test with p ≤ 0.05.
- No per-label held-out accuracy regression.

Raw outputs, per-label results, the exact policy, dataset hash, candidate hash, and method name are stored. Failure, no gain, or insufficient evidence leaves the candidate available for inspection but creates no promotion artifact. Promotion records an approved artifact within that experiment; it does not replace any installed model or globally deploy a candidate.

The test set is held out from optimization within each experiment. It is **not cryptographically hidden from the user or a malicious local model server**. Repeated use of the same benchmark is exploratory and weakens fresh confirmation. Use newly authored independent tests for consequential decisions. Exact duplicate inputs are rejected across all splits; semantic near-duplicates are not automatically detected. Model-name changes at a running inference endpoint can invalidate a comparison; keep the served model fixed throughout a run.

## Control, data, and limits

- The worker is a separate process with Linux address-space and core-dump limits, a hard wall-time alarm, bounded epochs, bounded output/context, and pre-dispatch inference-call reservations. Paused time counts against wall time. A failed or interrupted inference still consumes its reservation.
- These limits bound **the laboratory worker**, not an independently running inference server's RAM, VRAM, CPU, context allocation, or any service behind it. Configure those limits in your engine. Native classifier training uses CPU and one process.
- Emergency stop terminates the worker, escalates to kill after two seconds, and retains atomic artifacts. A separate model server may finish an already dispatched request. A provider request times out after 30 seconds; pause takes effect at the next boundary.
- Training checkpoints pair weights with an epoch cursor in an atomic JSON file. SQLite records state and decisions. A crash can lose an unfinished epoch or uncompleted inference pair, which will be retried within remaining budgets. Final verification recovery never changes the selected candidate.
- No file crawling, private-conversation collection, automatic uploads, generated-code execution, source editing, model rewriting, or shell tools are exposed to the mentor. Returned mentor commands are validated data in a fixed schema.
- User datasets need an explicit license or permission declaration. This release uses only the supplied training split; it does not generate synthetic training data or assume model-provider outputs may be used for distillation. Licenses still require human review for actual intended use.
- Local experiment text and snapshots are stored unencrypted. Use filesystem permissions/encryption as appropriate. There is no telemetry. Cloud mentoring sends only explicitly authorized objective/model/hardware and training/validation context. Unrelated previous experiment text is excluded from cloud context.

## Capability status

| Status | Capability |
| --- | --- |
| Implemented and exercised | CPU SGD weight training, baseline and independent final evaluation, artifact hashes, promotion gating, saved student reuse, SQLite history, hard worker limits, pause/resume/stop, checkpoint recovery, CLI |
| Implemented and exercised live on one setup | OpenAI GPT-4.1 mentor → Ollama Qwen2.5 1.5B prompt optimization, baseline/candidate evaluation and promotion; see the sanitized result above |
| Implemented; automated fixture coverage, additional live verification pending | Anthropic mentor, local/compatible mentors, LLM-directed SGD, lexical retrieval augmentation, saved prompt/retrieval inference; external engines/credentials required |
| Implemented; graphical verification pending in restricted build environment | Native GTK desktop, configuration, local-sharing permission, live journal, resource summary, artifact viewer, classifier trial |
| Future | LoRA/QLoRA/SFT for generative models, semantic/vector RAG, dataset discovery, permitted synthetic data/distillation, custom evaluators, stronger external inference resource isolation, automatic model-server checkpoint export, source-change proposals with approval |

No generative-model LoRA, QLoRA, SFT, multi-task learning, automatic continual learning, or general intelligence training is implemented. Saved classifier weights can be reused manually; stored experiment history is not continual weight learning. Retrieval is lexical selection of labeled training examples, not vector search. No LoRA job has been run or claimed. The NVIDIA driver was unavailable during development, so the application selected CPU training. Ollama GGUF inference artifacts are not assumed to be trainable Transformer checkpoints. Future LoRA support must use compatible original model weights, verified licenses, and hardware preflight, and preserve the original weights.

See the [Phase 2 guide](docs/phase2.md), [Phase 2 verification](docs/phase2-verification.md), [architecture](docs/architecture.md), [verification evidence](docs/verification.md), and [data license](DATA_LICENSE.md).

## License and contributions

Application code is licensed under [MIT](LICENSE), copyright Jim Wilks, 2026. The included benchmark has its separate [CC0 notice](DATA_LICENSE.md); external models, datasets, engines and libraries retain their own licenses. See [CONTRIBUTING.md](CONTRIBUTING.md) for issues, pull requests and secret checks, and the [beta release checks](docs/beta-release.md) for verification limits.
