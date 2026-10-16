# Phase 2: cloud mentor, local student

OVERMIND extends the existing GTK application and worker. Existing CPU training, datasets, experiment IDs, artifacts, recovery, and promotion policy remain available. Database migration only adds a `cloud_calls` ledger; it does not rewrite old runs.

## Launch and configure

```bash
./run.sh
```

Use the system Python 3.12+ with GTK 3 (`python3-gi` and `gir1.2-gtk-3.0` on Pop!_OS/Ubuntu). No new pip dependency is required.

1. Select **OpenAI · cloud mentor** or **Anthropic · cloud mentor** in the existing mentor card.
2. Enter a masked, session-only API key, or launch OVERMIND with `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` set. `OVERMIND_OPENAI_API_KEY` and `OVERMIND_ANTHROPIC_API_KEY` take precedence over the generic environment variables. No key is written to a configuration, artifact, log, or key file. Session keys are held in memory and handed only to the selected worker through its environment; they must be re-entered after restart unless supplied externally.
3. Click **Discover models**, choose an accessible text-generation model, then **Inspect connection**. These actions use authenticated model metadata endpoints, **not paid generation probes**. A successful inspection explicitly reports that inference has not yet been tested. Listed models may include models unsuited to mentoring; unsupported generation requests fail visibly.
4. Select **Ollama · local LLM** for the student. Click **Discover models** to detect the executable, server, installed models, sizes and digests returned by `/api/tags`. Pick an installed model and inspect its architecture, quantization, capabilities and license. **Test local inference** sends one bounded local readiness request.
5. Describe the objective and choose a licensed dataset with explicit labels and train/validation/test splits. The included support-routing benchmark is available. Current independent evaluation supports exact-label text classification, not arbitrary open-ended capability assessment.
6. Set candidate count, wall time, inference-call count and worker memory. Enter the cloud run budget and **upper-bound input/output USD-per-million-token rates for the exact selected model**, using its current official pricing. Defaults are zero and block cloud generation. Changing the mentor model/provider clears authorization and rates.
7. Explicitly authorize paid calls for this run and cloud sharing of the objective, hardware/model details and selected training/validation data. Separately allow local dataset dispatch for the student. Held-out examples and their answers are never sent to the mentor. Unrelated earlier experiments' text is excluded from cloud context.
8. Click **RUN EXPERIMENT**. The existing Laboratory page shows phase, decisions, candidate measurements, token totals, charged/reserved cost and limits. Evidence & artifacts includes `billing.json` and the final promotion report.

The key does not grant spending permission by itself. The run requires both authorization booleans and positive configured budget/rates. Connection discovery does not grant generation permission. This development phase made no paid API requests.

## Ollama and hardware

OVERMIND never installs Ollama, downloads models, or starts its service automatically. Follow the [official Ollama Linux instructions](https://docs.ollama.com/linux), start its service (or run `ollama serve`), and provision a suitably licensed small model yourself. Discovery distinguishes an installed executable from a reachable inference server and an empty model inventory. A reachable server is usable even if its executable is not on the application's PATH.

The hardware panel uses actual `/proc/meminfo`, CPU counts, load and `nvidia-smi` results. It does not assume the requested 32 GB RAM or GTX 1080 Ti is accessible. During verification, this environment reported approximately 15.5 GiB RAM and no working NVIDIA driver. Ollama was installed but the server was unreachable from this execution environment.

Consumer hardware can run the implemented prompt/retrieval experiments without a training runtime: Ollama performs student inference; the mentor runs remotely. Use an appropriately small/quantized model for the resources actually available. Worker memory limits do **not** bound the separate Ollama process's RAM/VRAM. Configure that server independently. This phase did not provision or benchmark a local LLM.

## What the mentor actually controls

The mentor receives bounded hardware/model metadata, the learning objective, balanced training examples, a validation summary with per-label accuracy and representative failures, baseline and best validation accuracy, remaining cloud cost information, and persistent candidate history for this run. It chooses a validated command:

- `prompt_optimization`: propose a system prompt that the local student actually uses during validation.
- `retrieval_augmentation`: propose a system prompt and choose 1–4 reference examples retrieved by a deterministic lexical scorer from the licensed **training split only**. Retrieval executes locally for each request.
- With the existing CPU classifier student: select a bounded SGD learning rate; real weight training remains available, and the mentor can revise its rate every six epochs.

The commands are executable laboratory operations represented by a fixed JSON schema. There is no shell, arbitrary Python execution, source modification, or arbitrary tool URL. The cloud does not merely narrate a hypothetical experiment: the worker uses the returned prompt, retrieval configuration, or learning rate, evaluates the actual student and returns validation evidence to the next planning turn.

Each LLM candidate is saved as `candidate-N.json`, with its actual predictions in `validation-N.json`. The mentor's returned command and rationale persist as `mentor-N.json`; candidate history persists in SQLite. Later planning turns see previous measured accuracies and reasons, enabling changes after unsuccessful candidates. Invalid commands, API failures, or exhausted budgets stop visibly rather than inventing a result. No implicit paid retry is performed.

After the candidate limit is reached, the best validation artifact is frozen. The existing independent evaluator compares the baseline and candidate on held-out inputs using supplied answers and the unchanged strict promotion rule. Ollama digests, when exposed by the server for the selected tag, are checked after baseline, before each candidate, and around final verification; a changed digest cancels comparison. Other inference engines may not expose an immutable identity.

**Prompt and retrieval changes do not update LLM weights.** Their saved checkpoint is a reproducible configuration/reference-corpus artifact, not new model weights or a LoRA adapter. The CPU student's weight artifacts remain genuine trainable weights. No LoRA/SFT job, model import, or adapter export is claimed in Phase 2.

## Spending and credential boundary

Cloud transport uses fixed official HTTPS hosts: OpenAI Responses (`/v1/responses`) and Anthropic Messages (`/v1/messages`). Credential headers never enter model context. Redirects and environment proxies are disabled. HTTP failures use fixed, actionable messages without echoing provider bodies, headers or credential values. Persistence also redacts known session/environment credentials from configurations, events, state and artifacts. Raw credential fields in configuration are rejected.

Before each paid dispatch, SQLite atomically reserves cost against the run budget. The conservative input estimate is the UTF-8 JSON request byte length plus 4,096 framing tokens; output reserves the configured total output token cap, including reasoning tokens where accounted by the provider. Costs use integer microdollars with upward rounding; authorization budgets round downward. There is no web search, tool billing, caching request, streaming, batch execution, or automatic retry enabled.

Successful valid usage reconciles the reservation to provider-reported input/output tokens at the configured rates. Cache-read/creation input counts are included if Anthropic reports them. Failed or interrupted requests with unknown usage retain their full reservation across restart. Known usage from an incomplete generation is recorded even though the command fails. A usage overrun is persisted, cancels the operation and latches further cloud dispatch closed for that run. Emergency termination cannot cancel a request already accepted by the provider; its reservation remains charged locally until the run ends.

**The budget is enforced locally at the rates you entered.** It cannot override provider invoices, incorrect/stale pricing, token-accounting behavior beyond the assumed reservation bounds, or spending by other applications. Set provider-side account/project limits as appropriate. Input/output rate entries must conservatively cover the exact chosen model and any applicable pricing tiers. `billing.json` is an estimate/usage ledger, not a provider invoice. Metadata calls do not appear in the generation ledger.

The existing hard wall-time alarm, address-space cap, call count, pause/resume and emergency stop remain. Local inference trials outside experiments are separately initiated one-at-a-time actions and do not change benchmark scores or the run's cloud budget.

Provider outputs are used as operational prompts/configuration and explanations. They are **not** converted into synthetic training labels or used for distillation/weight training. Review provider, model and dataset terms for the intended use. Synthetic generation remains blocked; Phase 2 does not assume commercial outputs may train competing models.

## CLI configuration and testing

Discover metadata without making paid generation calls:

```bash
./run.sh ollama
./run.sh models ollama
./run.sh models openai
./run.sh models anthropic
./run.sh hardware
```

Set the appropriate key in the launching environment without putting its literal value in shell history, for example:

```bash
read -rs OPENAI_API_KEY
export OPENAI_API_KEY
```

Use `ANTHROPIC_API_KEY` for Claude. API credentials are independent of a ChatGPT/Claude consumer subscription.

Copy [`examples/cloud-mentor.json`](../examples/cloud-mentor.json) to a working configuration. Select actual discovered mentor/student IDs, enter current positive rates and a positive budget, and explicitly set `authorized` and `data_sharing` to `true` **only when you intend to permit paid calls and cloud dataset dispatch**. For Claude, change `mentor.kind` to `anthropic`. Then:

```bash
./run.sh run --config /path/to/authorized-config.json
# Or use an explicitly licensed custom benchmark:
./run.sh run --config /path/to/authorized-config.json --dataset /path/to/dataset.json
./run.sh show EXPERIMENT_ID
./run.sh predict lab-data/EXPERIMENT_ID/candidate.json 'Please refund my payment' --allow-local-inference
python3 -m unittest discover -s tests -v
```

CLI invocation with an authorized configuration is the explicit dispatch grant; no credential lives in that file. The checked-in template is deliberately disabled and cannot initiate a paid request. API errors are not automatically retried. Recovery requires re-supplying credentials and uses the original run's persisted reservations and limits; it does not reset spending.

## Verification status

The original 17 tests pass. Additional bounded fixture tests exercise both official protocols, model discovery, usage parsing, reservations/reconciliation, secret redaction, failed-request retention, authorization rejection, changed-model detection, saved artifact trials and the cloud-mentor/local-student orchestration. Fixture outputs are clearly labeled tests and are **not model performance evidence**.

A saved live experiment completed with OpenAI GPT-4.1 and Ollama Qwen2.5 1.5B: prompt optimization increased this benchmark's held-out score from 33/40 to 39/40, with promotion under the implemented policy. This is a prompt change, not weight training or general-purpose learning. The [sanitized summary](../examples/qwen-prompt-result.json) excludes credentials, raw prompts, user configuration and local paths. Anthropic and retrieval pipelines have automated fixture coverage but no published live improvement result. No paid calls were made during release preparation. GTK interactive verification still requires the user's normal desktop session. See the [verification record](phase2-verification.md).

## Why prompt/retrieval first

[Ollama's import documentation](https://docs.ollama.com/import) describes importing compatible models/adapters; that is not an Ollama training API. [PEFT quantized LoRA training](https://huggingface.co/docs/peft/main/en/developer_guides/quantization) requires a compatible training model, libraries and hardware configuration. No working NVIDIA device or compatible training checkpoint was available here. Prompt/retrieval experimentation is implemented because it can execute against the already served local model without claiming weight updates. LoRA remains a separate future backend, not a decorative selector.

API references: [OpenAI text generation](https://developers.openai.com/api/docs/guides/text), [OpenAI models](https://developers.openai.com/api/reference/resources/models/methods/list), [Anthropic Messages](https://platform.claude.com/docs/en/api/http/messages/create), [Anthropic models](https://platform.claude.com/docs/en/api/http/models/list), and [Ollama installed-model discovery](https://docs.ollama.com/api/tags). Current rates must be checked against [OpenAI pricing](https://developers.openai.com/api/docs/pricing) or [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).
