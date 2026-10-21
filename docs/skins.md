# GAFAW skin format v1

Open **07 Skin Library** in `./run.sh`. Black Titanium is the first/default built-in skin; Phosphor Night is a texture-free alternative. Choose a skin and **Apply selected skin** to switch the existing GTK widgets immediately, without restarting or stopping an experiment. **Restore Black Titanium** returns to the default. The choice persists across launches. Invalid startup selections fall back to Black Titanium with a visible status message; a failed live apply retains the previous skin.

**Import .gafawskin** installs a validated local package, then selects it in the library for review. Apply is a separate explicit action. **Export selected skin** exports either a built-in or installed skin to a new filename. Existing files and installed IDs are never overwritten. Custom forks need a new manifest ID; built-in IDs are reserved.

The source-checkout application stores packages and selection in the ignored `skin-library/` directory beside `run.sh`, separately from experiment data. This directory must be writable for installation/persistence. No migration or changes to existing laboratory databases are required. Application code is in `overmind/skins.py`; the shared GTK stylesheet, built-in manifests, and skin textures live under `overmind/skins/`. The application emblem stays a separate brand asset. `python3 tools/generate_skin.py` regenerates the original Black Titanium textures and emblem.

[View the working Skin Library](screenshots/skin-library.png) (real GTK offscreen capture).

## Package structure

A `.gafawskin` is a ZIP with regular **files**, not directory entries:

```text
manifest.json
assets/panel.svg
assets/button.png
```

No Python, JavaScript, CSS, font binaries, executable hooks, web references, or code plugins are accepted. A skin cannot change widget actions, visibility, layout, disabled behavior, focus-outline rules, or experimental logic. Fonts refer to already installed system families, with normal GTK fallback. Authors remain responsible for contrast/readability; the engine preserves native controls and focus rings, but does not certify accessibility of arbitrary color choices. There is no online marketplace or editor.

## Manifest

```json
{
  "format": "gafaw.skin.v1",
  "id": "my-copper-lab",
  "name": "My Copper Lab",
  "version": "1.0.0",
  "author": "Your name",
  "license": "MIT",
  "description": "A personal copper instrument panel.",
  "font": {"family": "DejaVu Sans", "size": 13},
  "colors": {
    "background": "#201911",
    "text": "#fff0dc",
    "muted": "#dac7ab",
    "accent": "#ffc77e",
    "focus": "#ffe0a8"
  },
  "surfaces": {
    "header": {"texture": "assets/panel.svg"},
    "sidebar": {"background": "#302419"},
    "panel": {"gradient": ["#58422b", "#30251c"], "border": "#b08d61"},
    "button": {"gradient": ["#725638", "#423222"], "foreground": "text"},
    "button_hover": {"background": "#79603e"},
    "button_active": {"background": "#382718"},
    "button_disabled": {"background": "#37302a", "foreground": "#b0a59a"},
    "metric": {"background": "#1d180c", "foreground": "accent"}
  }
}
```

Required fields: `format`, `id`, `name`, `version`, `author`, `license`. IDs match `[a-z][a-z0-9-]{0,47}` and identify immutable installed packages; increment the ID (for example `my-copper-lab-v2`) to install another version alongside an existing one. Metadata strings are bounded; name/version/author/license are at most 200 characters, description at most 1,000. Format `gafaw.skin.v1` defines the schema; `version` is the author's release label. Unknown fields are rejected. Future schema versions can extend the declarative vocabulary without permitting execution.

`font`, `colors`, `surfaces`, and `description` are optional. Font family permits letters, digits, spaces and hyphens, at most 80 characters; body size is an integer from 11–24 pixels. Specialized title/metric/monospace text keeps its existing role-specific sizing/family. The five palette keys shown above are the complete v1 palette; literal colors are six-digit `#RRGGBB`. A surface can refer to a palette color explicitly defined in its manifest. Omitted settings inherit the shared Black Titanium base styling.

Supported surface keys:

| Surface | Native widget/style |
| --- | --- |
| `header`, `sidebar`, `panel`, `metric` | Header bar, sidebar, cards, LCD readouts |
| `button`, `button_hover`, `button_active`, `button_disabled` | Default, hover, pressed/checked, disabled button states |
| `button_primary`, `button_danger` | Primary and emergency actions |
| `input` | Entry/spin/combo/text input surfaces |
| `notebook`, `tab`, `tab_active` | Tab strip and tab states |
| `list_selected` | Selected experiment row |
| `progress_trough`, `progress` | Progress track and fill |
| `selection` | Text selection |

Each surface accepts optional `foreground`, `border`, and **one** background source: `background` (solid color), `gradient` (2–4 colors, top to bottom), or `texture` (an asset path). Colors/references are validated before the engine generates GTK CSS. Properties such as opacity, display, arbitrary selectors, dimensions, URLs, and raw CSS are not part of this format. Existing role-specific CSS specificity remains in effect: primary/danger/disabled states can override the generic button style, so authors should set those surfaces when changing the overall button appearance.

## Asset and archive validation

- Up to 32 assets; ZIP/expanded package limit 8 MB. Manifest ≤64 KB; each asset ≤2 MB. Images must have numeric positive dimensions no greater than 4096×4096.
- Assets must be `.svg` or `.png` under `assets/`. PNG signatures/IHDR dimensions are checked; GTK's image loader handles image decoding. A valid header alone does not certify the remaining PNG data.
- SVG permits only static `svg`, `defs`, gradients/stops, groups, paths, rectangles, circles/ellipses, lines and polygons. Attributes have a closed allowlist. Internal gradient references such as `fill="url(#metal)"` are allowed. No scripts, images, hyperlinks, foreign objects, event handlers, external references, entities, document types, or XML processing instructions (including XML declarations/stylesheets) are accepted. Strip an XML declaration when authoring an SVG for v1. Shape count and attribute lengths are bounded.
- Absolute paths, `..`, `.`, empty path components, backslashes, duplicate entries, links, special files, encrypted entries, oversized entries, and unsupported content are rejected. Packages are read and validated without ZIP extraction. Only validated images are materialized into a temporary directory for GTK; that cache is cleaned when the provider is replaced or the window is destroyed.
- Installation reserializes validated content; exports use private mode-0600 files and refuse overwrites. Skins are visual data, not authenticated/trusted publishers or software extensions. No imported code is executed.

## Create a package

Export a built-in from the UI as a reference. Edit the manifest with a new ID and your license/author metadata, and supply your own static assets. This local authoring command creates a package without directory records:

```bash
python3 - <<'PY'
from pathlib import Path
import zipfile
source = Path('my-skin')
with zipfile.ZipFile('my-copper-lab.gafawskin', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
    archive.write(source / 'manifest.json', 'manifest.json')
    for path in sorted((source / 'assets').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(source).as_posix())
PY
```

Import through Skin Library. The app validates the entire package before installation. It never executes authoring commands from a skin.

## Verification

```bash
python3 -m unittest discover -s tests -p test_skins.py -q
python3 tools/desktop_smoke.py --skins --experiment
```

Five focused tests cover multiple installed skins, byte-preserving asset export/import, saved selection, reserved IDs, duplicate/path/link/size rejection, code/CSS/font/unsafe-SVG rejection, invalid packages and safe built-in availability. The real GTK smoke exports/imports a custom skin, switches the existing provider, verifies saved selection, restores Black Titanium, and completes the existing CPU experiment with integrity/chart/failure/notebook checks. Manual screen-reader/HiDPI and broad theme/terminal combinations remain unverified.
