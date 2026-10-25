# Native UI planner (`--planner-mode tools`)

Optional planner mode: the same 4B model picks native UI actions (press,
type, keys, scroll, open_app, open_url, grounded click, wait, ask, confirm,
done, refuse, skill) via chat-template tool calls. There is no script tool —
no model-emitted AppleScript/JXA. App/analysis catalog intents stay planner
goals, never callable tools.

## Perception

Each planning turn gets a fresh screen context (`planner.context` traced
with `turn`, `chars`, `ocr`): the current frontmost window is screenshotted
and OCR'd at ~1 MP so toolbar-only AX trees (e.g. Numbers' cell grid) still
expose real content. The OCR feed never overrides privacy or relevance
gates — Muselet's own UI and chat-IDE windows (Devin, VS Code, Cursor,
Terminal, …) are never captured, and an empty/failed OCR falls back to the
AX text. `_verify_done` independently re-observes and re-captures screen
text for UI-only planners. Fresh evidence is not a guarantee of successful
completion; Numbers sorting still needs end-to-end validation.

## Enable

```sh
PLANNER=base PLANNER_MODE=tools BLIND_PLANNER=planner \
    tools/serve_brain.sh --planner-mode tools
```

The trailing `--planner-mode tools` override is needed because
`serve_brain.sh` forces the main planner to DSL mode for `PLANNER=base`.
DSL remains the default (`PLANNER_MODE` unset or `dsl`); all planner model
alternatives stay selectable via the existing env knobs.

## AX-first click resolution

A grounded `click "<target>"` first checks the live AX tree for an exact,
unambiguous enabled pressable control (button, radio, checkbox, popup,
menuitem, link, tab, row) whose label matches the target exactly, allowing
one role-word qualifier ("Organize radio button", "Add a Column dropdown").
A single unambiguous match is dispatched as an AX `press` through the same
safety gates as any ref press (danger-label confirmation, permission
checks); otherwise the screenshot/grounder path handles it unchanged.
Right/double clicks always skip AX resolution.

## Formula Facts

The Numbers cheat sheet includes the installed 14.5 `SORT` and `SORTBY`
signatures. These functions return a sorted copy into an empty destination,
not an in-place sort. The model must discover the source references and
choose the formula and destination; there is no formula-writing workflow
engine. Formula-based sorting still needs live validation.
