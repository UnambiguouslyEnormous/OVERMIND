# Phase 2 verification

## Completed live prompt experiment

A subsequently saved, completed experiment used **OpenAI GPT-4.1** as mentor and **Ollama qwen2.5:1.5b** as student. Its persisted report and candidate/dataset hashes were inspected during beta preparation; it was not rerun and no paid requests were made for that inspection.

- Method: prompt optimization; no student weight updates.
- Project-authored CC0 benchmark: 80 training, 24 validation and 40 held-out test examples.
- Held-out baseline: **33/40 (82.5%)**; frozen candidate: **39/40 (97.5%)**; gain: **15 percentage points**.
- Paired wins/losses: 7/1; exact one-sided p = 0.03515625; no per-label regression; promotion passed.
- Selected validation score: 24/24. Test cases were excluded from mentor context by the implemented pipeline.

The [sanitized public summary](../examples/qwen-prompt-result.json) contains only model identities and measured report fields. Raw local run configuration, prompts, logs and database are intentionally not published. The original private artifacts remain intact. This is evidence for one small routing benchmark, not fresh confirmation on a new benchmark or evidence of general intelligence. No live Anthropic, retrieval or generative weight-training result is claimed.

## Earlier implementation checks (historical)

The following checks were recorded on 2026-10-15 before the live result above. They describe the restricted development session, not the later user's run. No paid inference, model installation or large experiment was initiated by those checks. Current beta test results are in [beta release checks](beta-release.md).

| Check | Result |
| --- | --- |
| Existing tests | All 17 passed |
| New Phase 2 tests | All 19 passed |
| Combined suite | **36 tests passed** in 69.692 seconds |
| Python compilation | Passed |
| GTK import and stylesheet parsing | Passed |
| Desktop launch | Attempted; display connection denied/unavailable, so graphical launch remains unverified |
| Cloud API credential availability | OpenAI: absent; Anthropic: absent. Only presence booleans were inspected |
| Real OpenAI/Anthropic network/inference | Not run; requires credentials and explicit spending/data-sharing authorization |
| Ollama discovery | Executable installed; local endpoint unreachable from this environment |
| Live local LLM inference | Not verified |
| Full live cloud-mentor → Ollama-student experiment | Not run in this earlier check; subsequently completed as documented above |
| Existing saved weight artifact | Original SHA-256 preserved |
| Legacy database migration | Fixture verifies old run preserved; only additive cloud ledger schema |

The combined test suite includes actual CPU training from Phase 1. New cloud pipeline checks use explicit protocol fixtures, not real model responses or model-learning evidence. Both OpenAI Responses and Anthropic Messages paths execute the existing orchestration: metadata inspection, local baseline fixture inference, mentor analysis/planning, two controlled candidate operations, saved configurations/predictions, frozen-candidate verification and promotion rejection for no gain. The second mentor request contains the first candidate's measured validation result; held-out test examples never enter either cloud request. No fixture performance is presented as a product gain.

Security/control checks cover explicit authorization and cloud-sharing requirements, positive budgets/rates, official API payload/auth headers, no redirects, no unreserved paid generation, metadata-only connection checks, model discovery/pagination, fixed/redacted HTTP errors, pre-dispatch budget rejection, integer cost reconciliation, persistent uncertain/unfinished reservations, token-overrun lockout, missing usage, incomplete output, session key redaction, selected-credential worker inheritance, local-only manual artifact inference, changed Ollama digest rejection, bounded validation context, and retrieval restricted to training rows.

Raw test, launch, hardware and discovery logs remain local in ignored `docs/evidence/`; they are excluded from the public checkout. The environment reports approximately 15.5 GiB system RAM, 16 logical CPUs, and no working NVIDIA driver. These are observations, not the requested hardware assumptions.

Existing run `828cbca0f90a` remains present. Its weight file hash is still:

`f1278fcd02217b7ee4b0a278364c0da44886ccb1ebdbeb56ba3eb9b69f45a6f9`

The new suite uses temporary directories and does not rewrite that run's data. Phase 1's [verification report](verification.md) and evidence remain intact. The Phase 1 classifier gain is not reused as evidence of a Phase 2 cloud-mentored language-model gain.

## Run the remaining checks

Launch `./run.sh` from a normal logged-in Linux desktop session. Follow [Phase 2 setup](phase2.md): select a cloud provider, supply a session/environment API key, discover models, verify a reachable installed Ollama student, configure the exact model's current rate bounds and a small explicit spending budget, authorize sharing and paid use, then click RUN. This manually checks the new installation and its chosen provider/model combination; the saved OpenAI/Qwen result above does not verify every combination. A completed report can legitimately show no gain and reject promotion.

To reproduce local automated checks without credentials or paid calls:

```bash
python3 -m unittest discover -s tests -v
```

LoRA/QLoRA/SFT for generative models remain unimplemented; Phase 2 implements prompt/retrieval experiments against Ollama and preserves genuine CPU classifier weight training. No adapter import or GPU training is claimed.
