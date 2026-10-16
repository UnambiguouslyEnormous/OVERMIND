# Minimal Linux beta verification

Release preparation on 2026-10-15. This is a source-checkout beta, not a packaged installer. No repository publication, commit, push, history rewrite, paid API request or model download was performed.

## Changes and verification

- Permission migration now recognizes ownership before changing anything: a valid OVERMIND marker or the original `runs` and `events` SQLite schemas, with only laboratory entries at the root. New/empty dedicated directories are initialized with a private marker. The entire tree is checked before migration. Unrelated roots, invalid databases/markers, source/home/filesystem roots, symlink traversal, hardlinks and special files are rejected. Existing private experiment contents are not rewritten. The real saved laboratory passed a read-only recognition check; migration preservation is tested on temporary copies/fixtures.
- The machine-specific `.desktop` shortcut was removed. Existing `run.sh` is the portable source-checkout launcher; installation/startup instructions are in [README](../README.md#run).
- Public evidence consists of allowlisted [Qwen prompt](../examples/qwen-prompt-result.json) and [SGD classifier](../examples/classifier-result.json) summaries. Qwen's saved candidate and dataset hashes were checked against its report. Private configuration, raw prompts, databases, local paths and logs remain excluded. Earlier documentation links to ignored private artifacts were removed. The existing benchmark CC0 notice is unchanged; application code now has the requested MIT license.
- Full automated suite: **95 tests passed in 187.981 seconds**, including all 84 previous tests and 11 migration regressions. A final focused run passed **12 migration tests in 3.704 seconds**, including an additional FIFO/special-file regression added after the full run. All 96 current tests were therefore exercised across these runs. Cloud tests use mocks and synthetic credentials.
- Tracked-snapshot and reachable-history secret checks passed. A separate scan of current tracked/new working files found no matching secret patterns. These checks are not proof that arbitrary private data is absent; review staged changes before committing.
- A clean source copy containing only release-visible files was placed in a new path containing spaces, without `.git`, existing lab data or private configuration. From outside the checkout, its launcher passed help, hardware inspection, a full CPU classifier experiment, laboratory reopen/list, and saved-weight prediction (`billing`). The fresh experiment completed and promoted **10/40 → 37/40** held-out accuracy. No pip dependencies or network were needed.
- GTK launch was attempted from that copy and failed because the restricted environment could not initialize its display. No successful graphical launch is claimed. The copy used the already installed system Python/GTK; it was not a fresh OS dependency installation.

## Remaining checks before public beta

1. On a normal supported Linux desktop, follow the README from a fresh checkout and verify dependency installation, window startup, the built-in CPU experiment, evidence display, pause/resume/stop and reopening saved data. This is the remaining desktop release acceptance check; it cannot be completed in the restricted display environment.
2. Review the final staged diff and run `python3 -B -m overmind.secret_scan --staged` before the owner's commit. Include only source/docs and sanitized example summaries; never force-add private `lab-data/`, raw `docs/evidence/`, environment files or local configurations. Publishing is a separate owner action.

No additional model-training backend is required for this explicitly limited beta. Generative-model LoRA/QLoRA/SFT, general intelligence training, multi-task/automatic continual learning and vector retrieval are unimplemented. Lexical retrieval and Anthropic orchestration have fixture coverage, not a published live gain. GPU/other model combinations are not certified. An optional live rerun requires separately installed Ollama/model, explicit sharing/paid-use authorization and configured limits; it is not necessary to test the default CPU path. Never reuse the small benchmark as fresh statistical confirmation.

To repeat offline checks:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B -m overmind.secret_scan --tracked
python3 -B -m overmind.secret_scan --history
./run.sh --data /tmp/overmind-new-lab run
```

Choose a new/empty directory for the last command. Permission migration assumes exclusive, trusted ownership during opening; it is not a defense against another process maliciously swapping filesystem entries during preflight/migration. Private permissions are not encryption. See [security boundaries](security-hardening.md).
