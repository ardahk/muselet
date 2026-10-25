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

UI-only turns also get a **fresh AX observation every turn**: the act-diff
chaining that rebuilds the next observation text from act `diff_text` (the
DSL planner's speed path) is disabled for `ui_only` planners, so a dialog
opened by the previous action is seen with real refs instead of a stale
main-window view. When diffs are chained for the DSL planner, numeric AX
values are preserved: `slider`/`stepper`/`incrementor`/`picker` values and
Adobe Premiere's `clipSpeed` / `UI_HotText*` button values survive
`obsdiff`, so typed speed/duration values stay verifiable.

## Consecutive focus guard

`keys shift+3` in an app whose observed name starts with "Adobe Premiere"
is a Timeline-focus guess that may leave AX unchanged — a missing AX
change is not proof the shortcut failed, and the planner used to re-send
it indefinitely while "waiting" for evidence that may never arrive.
Within a task, a repeat `shift+3` against the same observed app+window is
refused before the RPC with model-facing feedback (`repeated_panel_focus`
in the trace); the model then picks a generic fallback or asks — the guard
does not guarantee the clip got selected and runs no deterministic
selection workflow. Any different action, a different window or a new task
permits the shortcut again; it only stops consecutive identical repeats.

## App discovery

Installed apps come from a shared recursive enumeration of `/Applications`,
`/System/Applications` and `~/Applications` (`AppResolver.installedAppURLs`;
skips hidden paths and `.app`/`.framework`/`.bundle` internals, includes
app symlinks). The brain resolves spoken names by normalized exact match,
then aliases, then a unique year-suffixed candidate — "premiere" resolves
`Adobe Premiere Pro 2026` inside its nested vendor folder; more than one
candidate asks "Which app?". The same enumeration backs the `apps` RPC
installed list.

## Regression coverage

Hermetic only (no live UI, no model loads):
`uv run --project ml python -m pytest ml/tests/test_obsdiff.py
ml/tests/test_premiere_focus_progress.py ml/tests/test_app_hints.py -q`
(63 tests) plus `ml/tests/test_first_use_fixes.py
-k identical_noop_presses_trip_loop_guard`. These cover the mechanics above;
they are not a live Premiere benchmark and do not claim end-to-end editing
success.

## Enable

```sh
PLANNER=base PLANNER_MODE=tools BLIND_PLANNER=planner \
    tools/serve_brain.sh --planner-mode tools
```

The trailing `--planner-mode tools` override is needed because
`serve_brain.sh` forces the main planner to DSL mode for `PLANNER=base`.
DSL remains the script default (`PLANNER_MODE` unset or `dsl`); tools mode
is what the current live demo build runs via the deployment override, and
all planner model alternatives stay selectable via the existing env knobs.
Tools mode exposes no arbitrary `script` tool — no model-emitted
AppleScript/JXA; the generic HandsKit adapters behind each tool are shared
with the DSL mode.

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
