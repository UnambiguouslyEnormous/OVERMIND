# Installation

OVERMIND **v0.2.0-beta.1** is a Linux source-checkout beta. Ubuntu 24.04 and compatible Pop!_OS installations are the primary targets; no other distribution is claimed as tested. A fresh graphical acceptance check is still pending, as recorded in the [beta notes](beta-release.md).

## Install and launch

Use Bash and system Python **3.12+**. Install GTK 3/PyGObject for the desktop:

```bash
sudo apt update
sudo apt install git python3 python3-gi gir1.2-gtk-3.0
/usr/bin/python3 --version
git clone https://github.com/UnambiguouslyEnormous/OVERMIND.git
cd OVERMIND
./run.sh
```

Ubuntu 24.04 provides [Python 3.12](https://packages.ubuntu.com/noble/python3) and [GTK 3 introspection bindings](https://packages.ubuntu.com/noble/gir1.2-gtk-3.0). For Pop!_OS, check the actual system Python before proceeding: compatibility requires Python 3.12+ and GTK 3 bindings. Older system Pythons are unsupported. Do not replace your distribution's Python to satisfy this requirement; choose a compatible installation.

Use a normal logged-in graphical session and leave virtual environments first (`deactivate` if one is active). The launcher uses `python3` on PATH; confirm `python3 --version` and `python3 -c 'import gi'` succeed. No pip package installation is required. The supported launcher locates its checkout even when called from elsewhere or from a path containing spaces. No binary package or desktop shortcut is shipped.

The default classifier needs no network, model download, GPU, or credentials after installation. For CLI-only use, Git, Bash, and Python 3.12+ suffice; GTK is only needed for the desktop.

## Updating

Stop active experiments, close the desktop, and back up your actual laboratory directory first, including any directory selected with `--data`. Keep that backup outside the checkout. Review source changes before updating:

```bash
cd OVERMIND
git status --short --branch
git pull --ff-only
./run.sh
```

Run the pull only after confirming the source tree is clean, or after committing/safely setting aside your edits. `git pull --ff-only` advances the configured upstream branch only if a fast-forward is possible. It does not switch to a release tag. If the branch has diverged, stop and inspect the history; do not use a forced reset or clean command. Preserve ignored experiment data and local settings. Review the [beta notes](beta-release.md) before upgrading.

## Troubleshooting installation

| Problem | Action |
| --- | --- |
| Python older than 3.12 | Use a compatible system installation. Older Pop!_OS releases may not meet the requirement. |
| `ModuleNotFoundError: gi` | Install the GTK packages above, leave virtual environments, and check which `python3` your PATH selects. |
| GTK cannot open a display | Launch from a normal logged-in graphical session. `./run.sh run` works without a display. |
| Update cannot fast-forward | Preserve edits and data, then inspect branch divergence; do not force a reset or clean the checkout. |

Continue with the [user guide](user-guide.md) for experiments, saved data, and provider setup.
