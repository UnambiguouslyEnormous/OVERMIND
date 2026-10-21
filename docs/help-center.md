# Offline Help Center and Stanley

Open **Help / User Guide** in the header, or press **F1**, for the focused field
or current workspace. The resizable guide stays separate from the workbench and
never blocks it. **Shift+F1** or the sidebar stapler opens **What’s This?** with
Stanley. Press Escape to hide either window.

The Help Center includes searchable bundled articles, Back history, Previous/Next
navigation, a Quick Start, and eight workflow walkthroughs. Existing `?` popovers
now offer **Learn More** and, when enabled, **Ask Stanley**. They all reference the
same maintained concept definitions. Search matches words in local article titles,
categories and bodies; it is documentation lookup, not a conversational AI answer.

## First experiment

1. Open Help and choose **Quick Start**.
2. Review the CPU-classifier configuration and included licensed classification
   dataset. The guide never resets settings or chooses a backend for you.
3. Choose **Show Control** to outline and focus the real control for a step.
   Walkthroughs can navigate tabs, but never edit values, import files, start jobs,
   perform inference, install dependencies or download anything.
4. Press **RUN EXPERIMENT** yourself when ready, then follow Laboratory progress.
5. The Quick Start’s evidence step requires a completed selected CPU-classifier
   run with verified updates and checkpoint reload. Inspect held-out results and
   the promotion decision independently; a successful mechanics check is not a
   claim of useful improvement.

Choose **Start / Restart**, **Resume saved walkthrough**, **Skip step** or **Leave
walkthrough** as needed. Tutorial progress and completion are shown locally. Next
records reviewed steps, not a scientific certificate. Skipped walkthroughs are
not marked complete; restart to review them. The LoRA and Playground walkthroughs
explain prerequisites and point to the existing controls without executing them.
A LoRA control hidden by another student choice stays hidden until you select the
appropriate student yourself.

## Stanley the Stapler

Stanley is GAFAW’s original office-supply assistant: **Chief Executive Office
Supply, GAFAW Laboratories**. He offers a short explanation first; **Explain More**
shows the underlying concept and **Open Guide** opens its article. His compact
window has Quick Start, offline search and an independent Always on Top choice.
He is deterministic and works without a language model or network connection.

Context priority is explicit topic, current/last meaningful focused control,
workflow/status, active tab, then general help. The launcher preserves field
context when it takes focus. Changing tabs or experiments clears stale fields.
Native GTK focus events and declared help IDs drive this; there is no pointer
polling or screen scraping. Context includes only public backend/stage categories,
not values from text fields, credentials, private examples, logs or responses.

Stanley’s original SVG scene has a hinged jaw, blinking/looking eyes, brief
speaking/greeting/confused/side-eye/celebrating/concerned gestures, and a sleepy
pose after three minutes without Stanley interaction. These are moods, never
metrics. Brief gestures sample at 12.5 frames/second; idle samples at 2/second.
Those are configured sampling rates, not a measured performance claim. Hidden or
static characters have no animation timer. GTK’s existing SVG icon loader renders
the vector art; no Cairo bridge, heavy framework, downloaded art or new package is
required. Regenerate an original contact sheet with:

```sh
python3 tools/render_stanley.py /tmp/stanley.png
# Or preserve vector source output:
python3 tools/render_stanley.py /tmp/stanley.svg
```

The artwork source and gestures in `overmind/stanley.py` are covered by the
repository’s MIT license. No Clippy assets or character design are used.

## Preferences and quiet operation

Expand **Help preferences** to disable Stanley completely, turn off dry humor, or
reduce motion. System GTK animation preferences are also respected. Disabling
hides the launcher/companion, stops their animation sources and hides Ask Stanley
links; Shift+F1 still opens the ordinary guide. The Help Center remains available.

Guide and companion geometry and Always on Top choices are remembered separately
on close or normal application exit. A desktop may ignore requested positioning
or stacking, especially under Wayland; these requests never make the windows modal.
The guide uses a stable reading palette so community skins cannot obscure its
text, and GTK retains keyboard navigation and accessibility descriptions.

Preferences are allowlisted private JSON (mode 0600), written atomically next to
the Skin Library directory: the default is `skin-library.help.local.json` in the
checkout. It stores window geometry, toggles and tutorial progress only, and is
ignored by Git. It is deliberately outside the experiment store and the Skin
Library’s validated package directory, so neither migration rules nor installed
packages change. Malformed preferences fall back to defaults; unsafe paths are
rejected, and save failures leave session settings usable with a guide notice.

Reactions are non-blocking and never summon a window. Only a newly observed worker
transition triggers completion/failure reactions; browsing a historical completed
run does not. Verified update/reload reactions require the actual report’s
integrity fields and positive counters. Preflight blocker reactions require a
parsed actual compatibility result, not guessed diagnoses from error strings.
Tutorial completion is distinct from experiment verification. Help never claims
improved reasoning, accuracy or style from a gesture or a completed job.

## Extending the shared framework

Follow [the contextual-help standard](context-help.md) and [AGENTS.md](../AGENTS.md).

- Add concept explanations to `help_content.TOPICS`; detailed articles automatically
  reuse their paragraphs. Add workflow articles to `help_guide.GUIDES` and route
  new short-help IDs in `SHORT_ROUTES`. No imported executable help/plugin format
  exists.
- Register intentional field help with `contextual`, `short_help`, `help_label` or
  `with_help`. Descendants inherit their containing section’s help when appropriate.
  Give launcher/navigation utilities `_gafaw_context_utility = True` to preserve
  the user’s last field when opening assistance.
- Add walkthrough `Step` definitions and an ordered `TUTORIALS` entry, using a
  stable target. Existing Desktop attribute names work; custom controls can use
  `app.help_system.register_target('my-feature.setting', widget)`. Target resolution
  must point to real widgets. Tutorials may navigate and highlight only.
- Add reactions at authoritative event boundaries. Route category-only messages
  through the controller, with evidence checks before any verification claim.
  Never pass raw exceptions, keys, dataset text or model output to Stanley.
- Keep search, content, routing and preferences independently testable without GTK
  or optional ML libraries. Animation must stop on hide, destruction, disable and
  reduced motion; event reactions must not open or focus windows.

Focused validation:

```sh
python3 -B -m unittest discover -s tests -p test_context_help.py -v
python3 -B -m unittest discover -s tests -p test_help_center.py -v
python3 -B tools/help_center_smoke.py  # requires desktop display
python3 -B tools/help_smoke.py         # existing contextual popover regression
python3 tools/parameter_smoke.py       # existing scroll/reset interaction check
```

The GUI checks use temporary stores and never train or call providers. Synthetic
status records exercise event routing; they are not GPU or training validation.
Manual screen-reader checks, multi-monitor positioning and every Linux compositor’s
stacking behavior remain outside those checks.
