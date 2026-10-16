# Beta readiness: v0.2.0-beta.1

This is a Linux source-checkout beta targeting Ubuntu 24.04 and compatible Pop!_OS installations. No other distribution is claimed as tested. There is no packaged installer. See [installation](installation.md) and the [user guide](user-guide.md).

| Purpose | Version |
| --- | --- |
| README and desktop display | `v0.2.0-beta.1` |
| Python package and `overmind.__version__` | `0.2.0b1` |
| Intended GitHub release tag (not created) | `v0.2.0-beta.1` |

## Verified checks

The beta preparation began from synchronized sanitized `main` at `9636fff3323fffcbc4f687c7b007b0432066d7da`. The recorded full offline suite passed **96 tests in 144.509 seconds**. Coverage includes actual CPU training, independent evaluation, lifecycle/recovery, provider protocol fixtures, bounded proposal corrections, spending authorization/accounting, credential isolation/redaction, and data migration rejection/preservation. Provider fixtures use synthetic credentials, not paid inference.

CLI help and installed GTK 3 bindings passed. A fresh temporary laboratory completed a CPU experiment, reopened through `list` and `show`, and predicted `billing` from saved classifier weights. A clean-source launcher check also worked from outside a checkout whose path contained spaces; its classifier comparison reproduced 10/40 → 37/40. The [experiment record](experiments.md#verified-results) preserves both the CPU result and the separate live Qwen prompt result.

Tracked-snapshot/history secret checks and a scan of proposed working files passed during preparation; these pattern checks do not prove that all sensitive content is absent. Existing experiment contents and history/billing rows were preserved during permission hardening, and later source changes were checked against file-preservation snapshots.

Four real screenshots are included in the [README](../README.md#screenshots). Visual privacy review found no exposed credentials or identifying paths; personal path prefixes are masked, leaving a generic directory suffix in Evidence. PNG checks found no embedded text/EXIF metadata or trailing data; the inspected Evidence redactions are opaque. Screenshot bytes were preserved when renamed. Some captures retain older version labels.

## Remaining checks before public beta

1. On a normal supported desktop, follow installation from a fresh checkout. Verify dependency installation, startup, a built-in CPU experiment, evidence display, pause/resume/stop, and reopening saved data. Earlier restricted-environment launches could not initialize a display; supplied screenshots do not establish this entire acceptance checklist. A fresh OS dependency installation has not been tested.
2. Review the complete source/documentation diff and screenshots. Before the owner's commit, stage only intended public files and run `python3 -B -m overmind.secret_scan --staged`. Keep private laboratories, raw logs, credentials, and local configurations excluded.

Additional live provider/model tests require separately installed engines/models, explicit sharing/paid-use grants, and configured limits. They are optional for the default CPU path. No broad provider, GPU, distribution, or general-capability certification is implied. [Capability limits](experiments.md#capability-status) and [security boundaries](security.md#limitations) remain part of the beta's scope.

## Repeat offline checks

```bash
python3 -B -m unittest discover -s tests -v
python3 -B -m overmind.secret_scan --tracked
python3 -B -m overmind.secret_scan --history
```

Use temporary data for smoke tests and retain backups of existing laboratories. Publishing, tagging, and release creation require separate owner action; this preparation does not perform them.
