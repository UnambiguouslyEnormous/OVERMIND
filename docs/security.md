# Security

OVERMIND is a single-user laboratory. These controls reduce accidental exposure and bound authorized operations; they do not make a hostile local engine or compromised host safe. Report suspected secret exposure privately through the repository host's private security-reporting channel if available. Never include a key in a public issue.

## Credentials and process isolation

- CLI stdout/stderr, argument errors, expected errors and unexpected application exceptions pass through redaction. Known retired keys remain redacted after replacement/clearing; environment credentials observed by the application are remembered for redaction. Provider-shaped keys and Bearer tokens are masked even when unregistered. Structured outputs additionally redact credential fields. Stream buffering covers ordinary split writes within a line.
- Credential-field rejection recursively inspects dictionaries, lists and tuples, including normalized field-name variants. Configuration, dataset snapshots, state and artifact writes reject credential-bearing structures. All persistence paths redact known values, including event kinds and billing model fields.
- Worker environments use an allowlist of ordinary runtime settings and only the selected mentor key. Other environment credentials, Python import overrides and loader overrides are not forwarded. Auxiliary hardware subprocesses receive the safe environment without any mentor key. The parent's environment is not changed.
- **Clear session keys** stops the active laboratory worker, clears the desktop entry/session authentication, disables environment fallback for the cleared providers, and resets spending/sharing authorization. Enter a new session key to reconnect, or restart to use externally configured environment keys. It does not revoke or alter the provider key. A provider request accepted before termination may still finish and its spending reservation remains intact.
- CLI/worker/desktop launch disables core dumps, sets a private umask, and sets Linux process dumpability to zero before accepting credentials. Failure to apply Linux dump protection fails closed. This reduces same-user process inspection and dump exposure without changing system-wide settings.

## Laboratory data

- Laboratory directories are `0700`; database, artifacts, temporary files, lock files and ignore markers are `0600`. Before migration, existing nonempty roots must have a valid `.overmind-lab` ownership marker or both original OVERMIND SQLite table schemas. Top-level contents must be laboratory files/run directories. New/empty dedicated roots receive the ownership marker. Home/filesystem/source roots, link traversal, unrecognized contents, symlinks, hardlinks and special files are rejected. Complete tree preflight precedes any mkdir/chmod/marker/database changes, so rejected paths have no migration side effects. Recognized legacy installations undergo permission-only hardening, preserving experiment rows and artifact contents. This is single-user migration, not protection against concurrent malicious filesystem changes by the same user. New files are explicitly private even when Store is used without the CLI entry point.

- `.gitignore` covers local environment files, credential/configuration files, logs, editor/runtime temporary files and known laboratory database/lock names. Safe `.env.example`, `.env.sample` and example JSON configurations remain visible. The rules do not ignore Python application modules such as `credentials.py` or `secrets.py`.
- Every dedicated laboratory directory receives a private `.gitignore` marker covering its contents, including when `--data` selects an alternate dedicated data directory. Unrelated nonempty directories are rejected without changes. Existing marker contents are preserved and the private rule is appended. A laboratory must not be the source/repository root. Ignore rules do not remove already tracked files; the scanner separately rejects private/ignored files proposed for commit.

Dedicated laboratory permissions are access control, not encryption. Permission migration requires exclusive trusted ownership; it does not defend against a same-user process swapping entries during preflight. Back up data before upgrading. No telemetry, private-conversation collection, file crawling, arbitrary generated-code execution, source editing, model rewriting, or shell tools are exposed to the mentor.

## Cloud spending

Cloud transport uses fixed official HTTPS hosts: OpenAI Responses (`/v1/responses`) and Anthropic Messages (`/v1/messages`). Credential headers never enter model context. Redirects and environment proxies are disabled. HTTP failures use fixed, actionable messages without echoing provider bodies, headers or credential values. Persistence also redacts known session/environment credentials from configurations, events, state and artifacts. Raw credential fields in configuration are rejected.

Before each paid dispatch, SQLite atomically reserves cost against the run budget. The conservative input estimate is the UTF-8 JSON request byte length plus 4,096 framing tokens; output reserves the configured total output token cap, including reasoning tokens where accounted by the provider. Costs use integer microdollars with upward rounding; authorization budgets round downward. There is no web search, tool billing, caching request, streaming, or batch execution. API errors are not automatically retried. Invalid-proposal corrections are limited to two and require separate reservations, as described in the [user guide](user-guide.md#mentor-response-diagnostics).

Successful valid usage reconciles the reservation to provider-reported input/output tokens at the configured rates. Cache-read/creation input counts are included if Anthropic reports them. Failed or interrupted requests with unknown usage retain their full reservation across restart. Known usage from an incomplete generation is recorded even though the command fails. A usage overrun is persisted, cancels the operation and latches further cloud dispatch closed for that run. Emergency termination cannot cancel a request already accepted by the provider; its reservation remains charged locally until the run ends.

**The budget is enforced locally at the rates you entered.** It cannot override provider invoices, incorrect/stale pricing, token-accounting behavior beyond the assumed reservation bounds, or spending by other applications. Set provider-side account/project limits as appropriate. Input/output rate entries must conservatively cover the exact chosen model and any applicable pricing tiers. `billing.json` is an estimate/usage ledger, not a provider invoice. Metadata calls do not appear in the generation ledger.

Check the exact model's current [OpenAI pricing](https://developers.openai.com/api/docs/pricing) or [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) before configuring rate bounds.

The hard wall-time alarm, address-space cap, call count, pause/resume and emergency stop remain. Local inference trials outside experiments are separately initiated one-at-a-time actions and do not change benchmark scores or the run's cloud budget.

Provider outputs are used as operational prompts/configuration and explanations. They are **not** converted into synthetic training labels or used for distillation/weight training. Review provider, model and dataset terms for the intended use. Synthetic generation remains blocked; provider outputs are not assumed to permit training competing models.

Every corrective cloud call consumes its own call and SQLite spending reservation. Token-cap failures reconcile reported usage; unknown usage keeps the conservative reservation. Corrections never reset cost, extend a grant, or increase the output cap. The [user guide](user-guide.md#cloud-mentors) explains setup and credential precedence.

## Worker and inference boundaries

- The worker is a separate process with Linux address-space and core-dump limits, a hard wall-time alarm, bounded epochs, bounded output/context, and pre-dispatch inference-call reservations. Paused time counts against wall time. A failed or interrupted inference still consumes its reservation.
- These limits bound **the laboratory worker**, not an independently running inference server's RAM, VRAM, CPU, context allocation, or any service behind it. Configure those limits in your engine. Native classifier training uses CPU and one process.
- Emergency stop terminates the worker, escalates to kill after two seconds, and retains atomic artifacts. A separate model server may finish an already dispatched request. A provider request times out after 30 seconds; pause takes effect at the next boundary.
- Training checkpoints pair weights with an epoch cursor in an atomic JSON file. SQLite records state and decisions. A crash can lose an unfinished epoch or uncompleted inference pair, which will be retried within remaining budgets. Final verification recovery never changes the selected candidate.
- Local experiment text and snapshots are stored unencrypted. Use filesystem permissions/encryption as appropriate. There is no telemetry. Cloud mentoring sends only explicitly authorized objective/model/hardware and training/validation context. Unrelated previous experiment text is excluded from cloud context.

## Local pre-commit check

The executable hook is supplied at `.githooks/pre-commit`. Enable it in each clone after reviewing it:

```bash
git config --local core.hooksPath .githooks
```

Hook configuration is local to each clone. If another hook framework is installed, integrate this command instead of replacing its configuration:

```bash
python3 -B -m overmind.secret_scan --staged
```

The hook inspects **index snapshots**, not unstaged working-tree edits, and honors Git's alternate index for partial commits. It blocks recognized OpenAI/Anthropic key patterns, private-key blocks, suspicious credential assignments and private/ignored paths, including force-added laboratory artifacts. It fails closed on Git inspection errors. Output contains redacted filenames and detection categories, never matching lines or values. Explicit test/example placeholders remain allowed; provider-shaped values are always rejected, including in examples.

Other offline modes:

```bash
python3 -B -m overmind.secret_scan --tracked
python3 -B -m overmind.secret_scan --history
```

`--tracked` scans all index snapshots. `--history` scans objects reachable from local refs without fetching, transmitting data or rewriting history. The application and scanner use only the Python standard library and existing Git executable.

## CI

`.github/workflows/secret-scan.yml` runs tracked-snapshot and reachable-history checks on push and pull requests. Checkout is pinned to a reviewed commit, uses read-only repository permissions, fetches history and disables persisted checkout credentials. No OpenAI/Anthropic credential, paid request, external scanner upload or secret-valued workflow input is required. See the [pinned checkout documentation](https://github.com/actions/checkout/tree/11bd71901bbe5b1630ceea73d27597364c9af683) for the checkout options.

Configure the check as required in branch protection if appropriate for your repository. Its presence is not evidence of a successful GitHub run; hosted CI status must be checked separately. CI cannot prevent the initial push of a leaked secret; use the local hook and provider/hosting push protection where available. Hooks are opt-in and can be bypassed; the workflow is not a replacement for review.

## Limitations

- Credentials still exist in Python/GTK memory and the selected worker's environment. Root/privileged processes, compromised code, system swap/hibernation, external debuggers and backups are outside these controls. OVERMIND does not reconfigure host encryption or erase shell history.
- Retired keys are retained in memory solely to keep redaction effective for the process lifetime. Clearing authentication cannot promise zeroization of immutable Python strings or revoke a key at the provider.
- Redaction and secret scanning are defenses against common accidents, not proof that all sensitive data is absent. Unknown formats, encoded/split secrets, arbitrary personal data, native writes bypassing Python streams and forced output flushes between secret fragments can evade pattern-based checks. Do not put credentials in datasets or prompts.
- Permissions provide access control, not encryption. Existing historical content is not rewritten. Use a dedicated owned laboratory directory; symlink-based legacy layouts require manual review/migration rather than automatic traversal.
- The scanner intentionally has no entropy-only detector or remote validation and may require review of false positives. Tracked examples are scanned for real-looking values too. CI uses checked-out scanner code; required review/branch protection is still needed to protect the check itself.


Regression coverage includes nested validation, retired-key redaction, split output writes, worker/auxiliary environments, process dump controls, private file modes, migration preservation and rejection, partial Git indexes, and secret-free scanner output. Tests use synthetic credentials and temporary fixtures. See [beta verification](beta-release.md#verified-checks) for the recorded full-suite result; desktop interaction still needs a normal session.
