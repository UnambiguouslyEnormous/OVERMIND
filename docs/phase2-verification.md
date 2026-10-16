# Phase 2 verification

Verified on 2026-10-15 in the supplied workspace. No paid inference, model installation or large experiment was initiated.

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
| Full live cloud-mentor → Ollama-student experiment | **Not verified**; no measured Phase 2 LLM improvement claimed |
| Existing saved weight artifact | Original SHA-256 preserved |
| Legacy database migration | Fixture verifies old run preserved; only additive cloud ledger schema |

The combined test suite includes actual CPU training from Phase 1. New cloud pipeline checks use explicit protocol fixtures, not real model responses or model-learning evidence. Both OpenAI Responses and Anthropic Messages paths execute the existing orchestration: metadata inspection, local baseline fixture inference, mentor analysis/planning, two controlled candidate operations, saved configurations/predictions, frozen-candidate verification and promotion rejection for no gain. The second mentor request contains the first candidate's measured validation result; held-out test examples never enter either cloud request. No fixture performance is presented as a product gain.

Security/control checks cover explicit authorization and cloud-sharing requirements, positive budgets/rates, official API payload/auth headers, no redirects, no unreserved paid generation, metadata-only connection checks, model discovery/pagination, fixed/redacted HTTP errors, pre-dispatch budget rejection, integer cost reconciliation, persistent uncertain/unfinished reservations, token-overrun lockout, missing usage, incomplete output, session key redaction, selected-credential worker inheritance, local-only manual artifact inference, changed Ollama digest rejection, bounded validation context, and retrieval restricted to training rows.

Raw evidence: [test log](evidence/phase2-tests.txt), [launch attempt](evidence/phase2-launch.txt), [hardware](evidence/phase2-hardware.json), [Ollama discovery](evidence/phase2-ollama.json). The environment reports approximately 15.5 GiB system RAM, 16 logical CPUs, and no working NVIDIA driver. These are observations, not the requested hardware assumptions.

Existing run `828cbca0f90a` remains present. Its weight file hash is still:

`f1278fcd02217b7ee4b0a278364c0da44886ccb1ebdbeb56ba3eb9b69f45a6f9`

The new suite uses temporary directories and does not rewrite that run's data. Phase 1's [verification report](verification.md) and evidence remain intact. The Phase 1 classifier gain is not reused as evidence of a Phase 2 cloud-mentored language-model gain.

## Run the remaining checks

Launch `./run.sh` from a normal logged-in Linux desktop session. Follow [Phase 2 setup](phase2.md): select a cloud provider, supply a session/environment API key, discover models, verify a reachable installed Ollama student, configure the exact model's current rate bounds and a small explicit spending budget, authorize sharing and paid use, then click RUN. This is the first opportunity to verify actual cloud authentication, model-specific generation compatibility, real mentor decisions and live student improvements. A completed report can legitimately show no gain and reject promotion.

To reproduce local automated checks without credentials or paid calls:

```bash
python3 -m unittest discover -s tests -v
```

LoRA/QLoRA/SFT for generative models remain unimplemented; Phase 2 implements prompt/retrieval experiments against Ollama and preserves genuine CPU classifier weight training. No adapter import or GPU training is claimed.
