# Credential security hardening

This patch addresses the confirmed read-only audit findings. It does not rotate provider keys, change account configuration, delete experiments, rewrite Git history, stage changes, commit, or push.

## Implemented protections

- `.gitignore` now covers local environment files, credential/configuration files, logs, editor/runtime temporary files and known laboratory database/lock names. Safe `.env.example`, `.env.sample` and example JSON configurations remain visible. The rules do not ignore Python application modules such as `credentials.py` or `secrets.py`.
- Every dedicated laboratory directory receives a private `.gitignore` marker covering its contents, including when `--data` selects an alternate dedicated data directory. Unrelated nonempty directories are rejected without changes. Existing marker contents are preserved and the private rule is appended. A laboratory must not be the source/repository root. Ignore rules do not remove already tracked files; the scanner separately rejects private/ignored files proposed for commit.
- CLI stdout/stderr, argument errors, expected errors and unexpected application exceptions pass through redaction. Known retired keys remain redacted after replacement/clearing; environment credentials observed by the application are remembered for redaction. Provider-shaped keys and Bearer tokens are masked even when unregistered. Structured outputs additionally redact credential fields. Stream buffering covers ordinary split writes within a line.
- Credential-field rejection recursively inspects dictionaries, lists and tuples, including normalized field-name variants. Configuration, dataset snapshots, state and artifact writes reject credential-bearing structures. All persistence paths redact known values, including event kinds and billing model fields.
- Worker environments use an allowlist of ordinary runtime settings and only the selected mentor key. Other environment credentials, Python import overrides and loader overrides are not forwarded. Auxiliary hardware subprocesses receive the safe environment without any mentor key. The parent's environment is not changed.
- **Clear session keys** stops the active laboratory worker, clears the desktop entry/session authentication, disables environment fallback for the cleared providers, and resets spending/sharing authorization. Enter a new session key to reconnect, or restart to use externally configured environment keys. It does not revoke or alter the provider key. A provider request accepted before termination may still finish and its spending reservation remains intact.
- CLI/worker/desktop launch disables core dumps, sets a private umask, and sets Linux process dumpability to zero before accepting credentials. Failure to apply Linux dump protection fails closed. This reduces same-user process inspection and dump exposure without changing system-wide settings.
- Laboratory directories are `0700`; database, artifacts, temporary files, lock files and ignore markers are `0600`. Before migration, existing nonempty roots must have a valid `.overmind-lab` ownership marker or both original OVERMIND SQLite table schemas. Top-level contents must be laboratory files/run directories. New/empty dedicated roots receive the ownership marker. Home/filesystem/source roots, link traversal, unrecognized contents, symlinks, hardlinks and special files are rejected. Complete tree preflight precedes any mkdir/chmod/marker/database changes, so rejected paths have no migration side effects. Recognized legacy installations undergo permission-only hardening, preserving experiment rows and artifact contents. This is single-user migration, not protection against concurrent malicious filesystem changes by the same user. New files are explicitly private even when Store is used without the CLI entry point.

## Local pre-commit check

The executable hook is supplied at `.githooks/pre-commit`. Enable it in each clone after reviewing it:

```bash
git config --local core.hooksPath .githooks
```

This setup command has **not** been run automatically; repository-local Git configuration is left to the owner. If another hook framework is already installed, integrate the following command rather than replacing its configuration:

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

The workflow has not been run on GitHub by this patch. Once pushed by the owner, configure the check as required in branch protection. CI cannot prevent the initial push of a leaked secret; use the local hook and provider/hosting push protection where available. Hooks are opt-in and can be bypassed; the workflow is not a replacement for review.

## Verification and limitations

Regression tests use synthetic credentials only and temporary repositories without committing anything. They cover the audited leaks, nested validation, key replacement/clearing, structured redaction, split output writes, allowlisted environments, hardware subprocess isolation, process dump controls, private modes under a permissive umask, existing data preservation, symlink/path rejection, Git ignore coverage, staged-versus-working-tree behavior, alternate Git indexes, private-file blocking, safe examples and secret-free scanner output.

**All 84 tests passed** (the existing 55 plus 29 security regressions) in 106.918 seconds. A final focused rerun of the 29 security tests also passed in 3.914 seconds. The current laboratory was hardened in place: all original file hashes and all experiment/history/billing rows remained identical; directories are now 0700 and files 0600. Tracked-snapshot, reachable-history and hook-command checks passed. A separate scan of tracked and new working-tree files found no matching secret patterns. The historical raw logs remain local in ignored `docs/evidence/`, excluded from the public checkout. Current results are summarized in [beta release checks](beta-release.md). Existing mentor/student protocol tests remain mocked; no live cloud authentication or paid experiment is claimed. The GTK clear-key handler is exercised without constructing a graphical window; interactive desktop behavior still needs a normal display session.

Remaining boundaries:

- Credentials still exist in Python/GTK memory and the selected worker's environment. Root/privileged processes, compromised code, system swap/hibernation, external debuggers and backups are outside this patch's protection. It does not reconfigure host encryption or erase shell history.
- Retired keys are retained in memory solely to keep redaction effective for the process lifetime. Clearing authentication cannot promise zeroization of immutable Python strings or revoke a key at the provider.
- Redaction and secret scanning are defenses against common accidents, not proof that all sensitive data is absent. Unknown formats, encoded/split secrets, arbitrary personal data, native writes bypassing Python streams and forced output flushes between secret fragments can evade pattern-based checks. Do not put credentials in datasets or prompts.
- Permissions provide access control, not encryption. Existing historical content is not rewritten. Use a dedicated owned laboratory directory; symlink-based legacy layouts require manual review/migration rather than automatic traversal.
- The scanner intentionally has no entropy-only detector or remote validation and may require review of false positives. Tracked examples are scanned for real-looking values too. CI uses checked-out scanner code; required review/branch protection is still needed to protect the check itself.

## Files changed for this hardening patch

Runtime changes: `.gitignore`, `overmind/security.py`, `overmind/__main__.py`, `overmind/desktop.py`, `overmind/hardware.py`, `overmind/lab.py`, and `overmind/store.py`. New scanner files: `overmind/secret_patterns.py`, `overmind/secret_scan.py`, `.githooks/pre-commit`, and `.github/workflows/secret-scan.yml`. Coverage/documentation: `tests/test_security.py`, this guide, README and security test logs. A private ignored marker was added inside the existing laboratory directory. The earlier uncommitted mentor-response fix is preserved alongside this patch.
