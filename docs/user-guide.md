# User guide

Install the prerequisites using the [installation guide](installation.md). The built-in CPU experiment needs no model download, GPU, credentials, or network connection.

## First desktop experiment

1. Keep **Curriculum controller** as mentor and **CPU text classifier** as student.
2. Leave the included CC0 support-routing benchmark selected: 80 training, 24 validation, and 40 held-out examples in four labels.
3. Keep the default limits and click **RUN EXPERIMENT**. The worker trains actual weights and selects a candidate using validation measurements.
4. Read the decisions in **Laboratory** and the final comparison in **Evidence & artifacts**. Promotion requires strict held-out accuracy improvement, a one-sided paired p ≤ 0.05, and no per-label accuracy regression.
5. Try a support ticket with the saved student. In a later run, select **Use saved student weights** to initialize from a previous classifier checkpoint.

The curriculum controller is deterministic. Changing the objective alone does not create a new task or architecture; a custom task needs an explicitly licensed dataset with appropriate labels and separate train/validation/test splits. [Evaluation details](experiments.md#what-the-measurements-mean) explain the small benchmark's limits.

## CLI commands

Run commands from the checkout root:

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

Commands containing `EXPERIMENT_ID` or `INTERRUPTED_EXPERIMENT_ID` require the ID printed by your run. Use your actual artifact path for prediction. CLI-only use needs no GTK bindings.

## Data and recovery

Persistent experiments default to ignored `lab-data/` inside the checkout. To use another dedicated directory, put `--data` **before** the command:

```bash
./run.sh --data "$HOME/overmind-lab" run
./run.sh --data "$HOME/overmind-lab" list
```

Use a new/empty directory or an existing recognized OVERMIND laboratory. The application rejects unrelated nonempty directories, home/source/filesystem roots, symlinks, hardlinks, and special files before permission migration. Do not work around rejection by removing markers or deleting data. Recognized laboratories receive private permissions; experiment contents remain unencrypted.

Do not run multiple desktop instances against the same laboratory. CLI runs are foreground processes; desktop controls apply to that desktop's worker. Closing the desktop stops its active worker and preserves completed checkpoints. Pause/resume works while the application remains open. After an unexpected worker exit, inspect the run and use `./run.sh recover INTERRUPTED_EXPERIMENT_ID` for a recoverable run. Recovery resumes frozen final evaluation without reselecting its candidate. [Runtime details](security.md#worker-and-inference-boundaries) describe interrupted work and worker limits.

## Local inference engines

Ollama and local OpenAI-compatible engines can fill mentor or student roles. OVERMIND does not install services or download models. Provision a suitably licensed model separately; see the [Ollama Linux guide](https://docs.ollama.com/linux). An independently running server can be used even if its executable is not on OVERMIND's PATH.

- **Ollama:** use `http://127.0.0.1:11434`, discover an installed model, and inspect its metadata. Discovery distinguishes a missing executable, an unreachable server, and an empty model inventory.
- **Compatible API:** use the root URL of a local engine exposing `/v1/models` and `/v1/chat/completions`, such as `http://127.0.0.1:8080`, without `/v1`. Inspection is limited to metadata the engine exposes.
- **Inspect connection** reports metadata, not successful generation. **Test local inference** sends one separately authorized, bounded readiness request. Neither action establishes a benchmark score.

Desktop experiments require explicit local dataset-sharing authorization. CLI use of a provider configuration authorizes that dispatch. Loopback-only transport does not guarantee the server itself is local: a server may proxy elsewhere, so review its deployment. Configure the separate server's RAM/VRAM limits yourself.

For an Ollama mentor directing CPU classifier training, save this as ignored `config.json`, replace the model ID, and run `./run.sh run --config config.json`:

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

A classifier checkpoint uses `{"kind":"linear","checkpoint":"/absolute/path/candidate.json"}`; it is copied before training, never overwritten. An LLM student uses a local provider object like the mentor's. The same local model can fill both roles; use separately named versions if you need distinct checkpoints. [Experiment methods](experiments.md#methods) explain what each configuration changes.

## Cloud mentors

OpenAI and Anthropic mentors are optional. Model discovery requires authentication but does not authorize paid generation. API credentials are separate from consumer ChatGPT/Claude subscriptions.

1. Select **OpenAI · cloud mentor** or **Anthropic · cloud mentor** in the mentor card.
2. Enter a masked, session-only API key, or launch OVERMIND with `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` set. `OVERMIND_OPENAI_API_KEY` and `OVERMIND_ANTHROPIC_API_KEY` take precedence over the generic environment variables. No key is written to a configuration, artifact, log, or key file. Session keys are held in memory and handed only to the selected worker through its environment; they must be re-entered after restart unless supplied externally.
3. Click **Discover models**, choose an accessible text-generation model, then **Inspect connection**. These actions use authenticated model metadata endpoints, **not paid generation probes**. A successful inspection explicitly reports that inference has not yet been tested. Listed models may include models unsuited to mentoring; unsupported generation requests fail visibly.
4. Select **Ollama · local LLM** for the student. Click **Discover models** to detect the executable, server, installed models, sizes and digests returned by `/api/tags`. Pick an installed model and inspect its architecture, quantization, capabilities and license. **Test local inference** sends one bounded local readiness request.
5. Describe the objective and choose a licensed dataset with explicit labels and train/validation/test splits. The included support-routing benchmark is available. Current independent evaluation supports exact-label text classification, not arbitrary open-ended capability assessment.
6. Set candidate count, wall time, inference-call count and worker memory. Enter the cloud run budget and **upper-bound input/output USD-per-million-token rates for the exact selected model**, using its current official pricing. Defaults are zero and block cloud generation. Changing the mentor model/provider clears authorization and rates.
7. Explicitly authorize paid calls for this run and cloud sharing of the objective, hardware/model details and selected training/validation data. Separately allow local dataset dispatch for the student. Held-out examples and their answers are never sent to the mentor. Unrelated earlier experiments' text is excluded from cloud context.
8. Click **RUN EXPERIMENT**. The Laboratory page shows phase, decisions, candidate measurements, token totals, charged/reserved cost and limits. Evidence & artifacts includes `billing.json` and the final promotion report.

An API key alone never grants spending permission. Both authorization booleans, a positive budget, and positive rate bounds are required. Local student readiness calls are separate from the cloud generation ledger. Read the [security and spending boundaries](security.md#cloud-spending) before enabling cloud use.

### CLI configuration

Discover metadata without paid generation:

```bash
./run.sh ollama
./run.sh models ollama
./run.sh models openai
./run.sh models anthropic
```

Supply a key through the desktop's masked session entry or an environment variable. In Bash, this avoids putting the literal key into shell history:

```bash
read -rs OPENAI_API_KEY
export OPENAI_API_KEY
```

Use `ANTHROPIC_API_KEY` for Anthropic. Never put keys in JSON configuration or prompts. Copy the disabled [cloud template](../examples/cloud-mentor.json) to an ignored local configuration, select discovered model IDs, and enter current conservative rates and a positive budget. Set `authorized` and `data_sharing` to `true` only when you intend paid calls and cloud sharing. For Anthropic, set `mentor.kind` to `anthropic`.

```bash
./run.sh run --config /path/to/authorized-config.json
./run.sh run --config /path/to/authorized-config.json --dataset /path/to/dataset.json
./run.sh predict lab-data/EXPERIMENT_ID/candidate.json 'Please refund my payment' --allow-local-inference
```

Paths and IDs above require substitution. Recovery requires credentials again and retains the original run's reservations and limits; it never resets spending. Authentication, quota, transport, refusal, and other API failures are not automatically retried.

## Mentor response diagnostics

Mentor proposals are validated data, never shell commands. Cloud requests use native JSON schemas: OpenAI Responses `text.format` and Anthropic Messages `output_config.format`. Unsupported structured-output models fail visibly without switching models or silently relaxing the schema.

Provider references: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) and [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs). The implemented cloud protocols are [OpenAI Responses](https://developers.openai.com/api/docs/guides/text) and [Anthropic Messages](https://platform.claude.com/docs/en/api/http/messages/create); model discovery uses their [OpenAI](https://developers.openai.com/api/reference/resources/models/methods/list) and [Anthropic](https://platform.claude.com/docs/en/api/http/models/list) metadata APIs, or [Ollama tags](https://docs.ollama.com/api/tags) locally.

The validator accepts a flat proposal or one unambiguous `experiment` wrapper. It rejects duplicate keys, mixed/conflicting structures, missing required fields, invalid types/ranges, whitespace-only or oversized prompts, invalid rationale, and unsupported strategies. Only validated operational fields execute; wrapper metadata is not interpreted as commands. Existing local mentor defaults remain supported.

A completed but invalid proposal can receive **at most two corrective requests** after the initial request. Empty/oversized responses and token-cap termination have distinct diagnostics. Corrections keep the same output cap and pass through authorization, reservation, call, time, and cancellation checks. Retry counters and concise feedback persist before dispatch, so restarts cannot reset the ceiling. Refusals and API failures do not receive corrective retries. Exhaustion marks the run failed and retains its baseline and completed artifacts; no fallback proposal or fabricated result is substituted.

`mentor-N-response-M.json` and `mentor_validation` journal entries record provider/model, proposal/request/retry counters, validation category, fixed messages, wrapper normalization, token usage, and cumulative charged/reserved cost. They exclude raw responses, objectives, samples, student prompts, API headers, and generated rationale. Only a concise validation error goes back as correction feedback. Candidate artifacts retain validated prompts, reference corpora, and rationale for reproducibility, with credential redaction; these private operational artifacts are different from diagnostic logs. Older saved evidence is not rewritten.

For repeated errors, inspect the categorized diagnostic and billing ledger before trying again. Leave a failed run intact and create a **new experiment**; failed runs are not resumable with `recover`. Never edit SQLite status or reset the spending ledger. A new paid run needs fresh authorization and repeats baseline evaluation against the current student.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Laboratory root rejected | Select a dedicated empty or recognized laboratory. Preserve the rejected directory and review [data protection](security.md#laboratory-data). |
| Another worker holds the lock | Stop the owning experiment normally; do not delete an active lock file. |
| Ollama unavailable | Check the separately managed server, model inventory, and `./run.sh ollama` output. |
| Cloud dispatch blocked | Check credentials, model compatibility, authorization, budget, and conservative rate bounds. |
| Mentor proposal rejected | Inspect the safe validation category; do not repeatedly launch paid runs without understanding it. |
| No promotion | Read the paired results and policy. No gain or insufficient evidence is a valid outcome. |

For installation/display problems, see [installation troubleshooting](installation.md#troubleshooting-installation). Report reproducible problems with sanitized diagnostics as described in [CONTRIBUTING.md](../CONTRIBUTING.md).
