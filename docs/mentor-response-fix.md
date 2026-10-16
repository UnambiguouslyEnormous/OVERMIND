# Cloud mentor response validation fix

## Confirmed cause

The saved response from experiment `79962b918903` is valid JSON with this shape:

```text
experiment
  name
  technique
  description
  system_prompt (string, 114 characters)
  retrieval_k
  reason
```

The old validator read `plan.get('system_prompt')` at the top level. The actual field was `plan['experiment']['system_prompt']`, so an existing valid prompt was reported as missing. It was not an empty/oversized prompt or JSON parsing failure. The connector had extracted JSON text successfully. The stored technique was retrieval augmentation. The baseline (79.2%), original response, billing and dataset are preserved in the original failed run. The recorded 1,478 input / 211 output tokens and approximately $0.000929 cost match the user's report.

The original saved proposal was checked offline against the repaired parser: it validates as retrieval augmentation with the same 114-character prompt, without any cloud or student call. Its contents are not reproduced in this document.

## Targeted changes

- `overmind/mentor.py`: shared proposal schema and validation. Accepts flat proposals and a single unambiguous `experiment` wrapper. Rejects mixed/conflicting structures and duplicate JSON keys. Distinguishes malformed JSON, missing fields, invalid types/ranges, whitespace-only prompts, oversized prompts, invalid rationale, and unsupported strategies. Cloud proposals require every field declared by the schema; existing local mentor defaults remain compatible. Only validated operational fields reach execution; wrapper metadata is not interpreted as commands.
- `overmind/cloud.py`: OpenAI Responses requests use strict `text.format` JSON Schema; Anthropic Messages requests use native `output_config.format` JSON Schema. Explicit provider token-cap termination is categorized separately from API errors. Empty/oversized completed responses can be corrected. API failures and refusals are not automatically retried. Unsupported structured-output models fail visibly rather than silently downgrading or changing the model.
- `overmind/lab.py`: at most two corrective requests after the initial request, through the existing authorization, cost reservation, token/call ceilings, cancellation and deadline checks. Retry counters and concise corrective feedback persist before dispatch, so a worker restart cannot reset the ceiling. Exhaustion uses the existing failed-run path and retains baseline and completed artifacts. No fallback proposal, generated label or fabricated decision is supplied.
- `overmind/providers.py` and `overmind/desktop.py`: bounded, allowlisted inspection summaries show model name, parameter size, stored size, quantization, context length and connection status. Full metadata is saved as `student-inspection.json`. Rendering an old inspection event also uses a concise summary without rewriting its stored event/history.
- `tests/test_mentor_responses.py`: mocked response and orchestration regression coverage.

Provider-supported formats follow [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) and [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs). Model support is required; no paid compatibility fallback is attempted. Output caps stay unchanged during correction, including after truncation; the feedback requests a shorter complete proposal.

## Diagnostics and privacy

New `mentor-N-response-M.json` artifacts and `mentor_validation` journal entries contain provider/model, proposal/request/retry numbers, acceptance/rejection, validation category, fixed actionable messages, wrapper normalization, reported token usage and cumulative charged/reserved USD. Corrective retries also appear in the journal. These diagnostics do not contain raw response text, objective, dataset samples, student prompt text, API headers or model-generated rationale. Only the concise validation error is returned as correction feedback; the rejected output is not echoed.

Executable candidate artifacts necessarily retain the validated system prompt, retrieval corpus and experiment rationale in the existing candidate history for reproducibility. Those are operational evidence, not diagnostic logs. Known credentials continue to be redacted by existing persistence protections. Previously saved raw responses and journal entries are preserved; this patch does not rewrite historical evidence.

Every corrective cloud call consumes a call reservation and receives a separate SQLite spending reservation before dispatch. Provider-reported usage is reconciled even for token-cap failures; unknown usage keeps the conservative reservation. No retry resets costs, extends a grant or increases output tokens. Authentication, quota, transport and other API errors stop without corrective retries. The configured local cost estimate still depends on the user's rate bounds, as documented for Phase 2.

## Verification

Tests use mocked cloud responses and temporary experiments. No real API credits are used. The tests cover the live wrapper shape reaching candidate evaluation, strict native request schemas for both providers, required fields, malformed/ambiguous JSON, empty and oversized prompts, invalid field types/strategies, truncation, API errors, first/second corrective success, retry exhaustion and persistence, cloud/call limit rejection, cancellation between retries, privacy-safe diagnostics, readable inspection summaries, and worker failure retaining baseline/diagnostic/billing artifacts.

**All 55 tests passed** (the original 36 plus 19 new regression tests) in 102.975 seconds. Python compilation, GTK imports and stylesheet parsing passed. The desktop launch was attempted but GTK could not initialize against the display in this restricted execution environment; graphical launch is therefore not verified here. These historical raw logs remain local in ignored `docs/evidence/`, excluded from the public checkout. Current results are summarized in [beta release checks](beta-release.md). A mocked pipeline verifies that accepted proposals reach candidate evaluation and final verification; it is not live LLM improvement evidence. The original run's four artifact hashes, failed status and 25 reserved calls were checked after the work and are unchanged.

## Safely rerun

1. Restart the application with `./run.sh` from the project directory so it loads the fix.
2. Leave failed run `79962b918903` intact. Create a **new experiment**; failed runs are not resumable through the existing recovery command. Do not edit SQLite status or reset the old spending ledger.
3. Select OpenAI `gpt-4.1-mini`, Ollama `qwen2.5:1.5b`, the same objective/dataset, two candidates, 240 calls and 2,048 output tokens. Keep your intended $0.25 budget and correct pricing bounds; no API configuration was changed by this fix.
4. Supply your session/environment credential and verify connections. Review sharing/spending permissions and click RUN only when you authorize new paid calls. Baseline evaluation will run again against the current local student; the previous baseline evidence remains available in the failed run.
5. Watch for `mentor_validation` acceptance and candidate evaluation. If invalid responses recur, inspect the categorized diagnostics and billing; after two corrections the worker stops gracefully. Do not repeatedly restart paid experiments without inspecting the error.

Live cloud-to-local execution was not rerun during this fix. Desktop graphical verification still depends on display access; the actual launch result is documented without claiming a successful launch when GTK cannot initialize.
