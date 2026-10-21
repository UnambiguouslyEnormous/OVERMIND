# GAFAW development standards

Preserve the launch path (`./run.sh`), existing experiments, datasets, checkpoints,
credentials, and spending/sharing protections. Keep optional ML imports out of GTK
startup. UI checks must use temporary stores; do not train models, download weights,
or call providers just to validate interface changes.

## Contextual help is required for new and changed UI

For each control, make an intentional choice:

- **Obvious action:** no help. Do not attach generic text to every widget.
- **Unfamiliar simple action:** one plain-English tooltip, ideally under 120
  characters, explaining the effect rather than repeating the label.
- **Technical concept, consequential setting, or tradeoff:** a focusable `?`
  button opening a short contextual popover (usually 2–5 short sentences).
  Explain what it changes, why it matters, and a sensible beginner approach.
  Add a short tooltip too only if it serves a distinct purpose.

Use the shared helpers in `overmind/context_help.py` and centralized definitions
in `overmind/help_content.py`; do not introduce giant hover text, modal help
windows, or a second help implementation. Keep explanations faithful to implemented
behavior, supported backends, units, consent boundaries, and measured evidence.
Update relevant help when behavior changes. Never describe prompting as weight
training or checkpoint integrity as proof of improved model quality.

Use `help_label(..., control=widget)` for technical settings, `with_help(widget,
key)` for standalone controls, and `short_help(widget, key)` for brief action tips.
`desktop.button(..., tip_key=key)` and `Desktop.card(..., help_key=key)` reuse these
patterns. Keep native widgets, their original state references, focus order,
keyboard editing, accessibility, scroll protection and live skin switching intact.

Every SpinButton, ComboBox and Range must declare a help ID using these helpers
(or `contextual` when a nearby group explanation covers it). A genuinely obvious
selector can use `no_help(widget, reason)` with a specific reason. The GUI audit
flags unexplained parameter controls instead of inventing automatic explanations.

Run focused checks for help/UI changes:

```sh
python3 -B -m unittest discover -s tests -p test_context_help.py -v
python3 -B tools/help_smoke.py       # requires a real GTK display
```

If parameter layout or interaction changes, also run
`python3 tools/parameter_smoke.py`. Do not run the full suite merely to edit help
copy. Report what was checked and any untested accessibility/display conditions.
See [the contextual-help guide](docs/context-help.md) for the implementation pattern.
