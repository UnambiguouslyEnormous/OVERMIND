# Contextual help

GAFAW uses intentional short tooltips and clickable `?` explanations throughout
its seven workspaces. Tab to a question mark and press Enter or Space, or click
it. Escape, Close, or clicking outside dismisses the popover. Closing returns
keyboard focus to its help button. Explanations are created only on first use;
exploring help never starts training or sends a model request.

## Choose the smallest useful explanation

| Control | Mechanism | Content |
| --- | --- | --- |
| Obvious action, such as Close | None | Avoid redundant interruptions. |
| Unfamiliar straightforward action | Short tooltip | One plain-English sentence, ideally under 120 characters; explain its effect. |
| Technical or consequential setting | Clickable `?` | Usually 2–5 short sentences: what it does, why it matters, tradeoffs, beginner guidance. |
| Related controls with one shared concept | Group-level `?`, plus intentional brief field tips | Explain once; avoid a question mark beside every obvious field. |

Use examples or warnings only when they explain real behavior. Units, supported
backends, data sharing, and limits must match the implementation. Distinguish
prompt-only changes, actual weight updates, reload integrity, and independent
quality evidence. Avoid a short tooltip that merely repeats its label or a long
popover that lists the whole roadmap.

## Reusable implementation

Definitions live in `overmind/help_content.py`, which imports neither GTK nor ML
libraries. Add a focused entry to `TOPICS` for a popover, or `SHORT_HELP` for an
action tooltip. Unknown keys fail immediately rather than leaving broken help.

```python
# help_content.py
TOPICS['training.example'] = topic(
    'Example training setting',
    'Explain the immediate effect in one short sentence.',
    'Describe what this setting changes in the implemented backend.',
    'Explain the practical tradeoff and a sensible starting choice.',
)

# Native GTK feature code
from .context_help import help_label, with_help, short_help

spin = Gtk.SpinButton.new_with_range(1, 10, 1)
row.pack_start(help_label('Example setting', 'training.example',
                          'subtitle', control=spin), False, False, 0)
row.pack_start(spin, False, False, 0)

# Standalone action or shared group concept:
row.pack_start(with_help(existing_widget, 'training.example'), False, False, 0)
# Short action explanation only:
short_help(existing_button, 'workshop.use')
```

Keep the original widget reference: wrappers return a container, while
`short_help` and `contextual` return the original widget. This preserves existing
callbacks, sensitivity changes, and value access. A group-level explanation can
cover a selector using `contextual(selector, topic_key)`, which attaches an
accessible description without a redundant hover tooltip. `no_help(widget,
reason)` records an explicit exemption for an obvious parameter selector.

`help_label` also associates its caption with the input for accessibility. Help
buttons expose descriptive accessible names, accept Enter/Space, and return focus
on dismissal. Native popovers provide outside-click dismissal; the bounded reading
area scrolls on small displays. Namespaced styles provide a stable contrast reading
surface across built-in and imported skins, without restyling the rest of the app.
Custom skins cannot execute or replace this implementation.

## Focused maintenance checks

```sh
python3 -B -m unittest discover -s tests -p test_context_help.py -v
python3 -B tools/help_smoke.py
```

The first check validates catalog brevity, focused explanations, and literal help
IDs in desktop code, without GTK. The real-display check opens every explanation
in every workspace, exercises keyboard and mouse events, Escape/Close and focus
return, and switches both built-in skins and a deliberately poor-contrast custom
skin. It also calls `missing_parameter_help` to flag unexplained selectors, spin
buttons and ranges, including dynamically added controls. A nearby group topic
can satisfy that audit through an explicit declaration; no generic help is added
automatically. These checks do not judge explanation accuracy: review the source
behavior when editing content. Manual screen-reader and varied-display checks
remain useful beyond the automated widget checks.

This standard applies to future interface additions as described in
[AGENTS.md](../AGENTS.md).
