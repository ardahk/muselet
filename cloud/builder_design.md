# Lane: design — native macOS menu-bar panel, kitten menu-bar icon, mascot fixes (user feedback, Sat evening)

Swift (uncompiled here; the lead compiles, runs and screenshots on the Mac) plus small Python/doc cleanups. Branch
`cloud/design` from `main`, one PR, one commit per numbered item. Files: `app/Sources/MuseletApp/Panel/*`,
`App/{MuseletApp,AppDelegate,Theme,TimerSettings,PermissionsModel,PlannerSettings,DebugHooks}.swift`,
`Mascot/{MascotController,MascotPaths,PillController,PillView}.swift`, `app/Sources/HandsKit/*` (timers),
`ml/src/brain/orchestrator.py` (timer hint), `docs/CLOCK_TIMERS.md`, `AGENTS.md`.

The user's words: "this is very very ugly overall design wise, we want it to feel native mac". He likes the kitten
mascot itself and its animations.

## 1. Menu-bar icon = the kitten
Today the status item shows a generic dark blob. Draw a monochrome **template** image (`isTemplate = true`, so macOS
tints it for light/dark/highlight) of the kitten's head silhouette: the two ears, round head, and the eyes as cut-outs.
Reuse the geometry in `MascotPaths.swift` so it matches the mascot, rendered at the standard 18 pt menu-bar size
(@1x/@2x crisp, no colour).

## 2. The panel is just Settings, native
Clicking the menu-bar icon opens settings directly. Remove the whole first page: the hero ("Hold right ⌥ to talk"),
"Last request", the example prompts, the "Connected" dot/text and the "Ready when you are" line. No custom brown/cream
palette in the panel: system materials, system font, standard controls, grouped `Form` sections like System
Settings (`.formStyle(.grouped)`), standard spacing, light and dark mode. Keep it compact (~340 pt wide).
Sections:
- **Permissions:** list only permissions that are NOT granted, each with the standard "Open System Settings" button.
  When everything is granted, hide the section entirely.
- **Models:** the 35B planner toggle (shown only on Macs with >= 48 GB, as today).
- **Memory:** the existing Settings › Memory content (on/off, list, search, delete) from PR #58.
- A plain "Quit Muselet" button at the bottom.
If the brain is disconnected, show one small native warning row ("Muselet's brain isn't running") instead of a
"Connected" label; show nothing when it's fine.
- **Debug section:** remove it from the panel. Everything it showed is already in `~/Library/Logs/Muselet/muselet.log`
  and `runs/traces/`. Keep the `DebugHooks` used by the screenshot script.

## 3. Timers: the Clock app is the only way, no Shortcuts, no setting
"It is stupid to have that timer on the settings; default should be using the app; remove all the code regarding
shortcuts and it shouldn't be a setting." Remove the Shortcuts backend entirely (the `Muselet Start Timer / Status /
Cancel` shortcuts, `ShortcutsRunning`, shortcut detection, the Settings › Timers section and `TimerSettings`
toggle, the brain's delayed shortcut-setup hint, the shortcut docs). `start_timer` drives Clock.app over AX
(`clock_ax`, PR #55); if that fails, Muselet's own timer is the silent fallback (keep it: benchmarks and
`hands probe timers` read its records). Update `timer_backend`/`timers` RPC fields, `docs/CLOCK_TIMERS.md`
(Clock AX only) and the RPC lines in `AGENTS.md`. Update the Swift and Python tests that referenced shortcuts.

## 4. The kitten must stay fully on screen
Today it can be dragged so it hangs off the left, right and bottom edges (top is already limited). Clamp the mascot
window so the whole kitten (and its bubble anchor) stays inside the screen's `visibleFrame` on drag (live, not only on
drop), on launch from the saved position, and on screen-parameter changes.

## 5. Keyboard close via the X button is still janky
Closing with the X button in the typing pill still collapses in a glitchy way (submit/Esc paths were fixed in #49).
Make the X path use exactly the same animated collapse + flicker-free focus hand-off as Esc. Test all paths.

## 6. The pill disappears as soon as the pointer leaves
"That keyboard and voice should fade away instantly when you move away from the kitten." Keep the 1 s hover dwell
to show it. Hide it with a quick fade (~0.12 s) the moment the pointer leaves the union of the kitten's frame, the
pill's frame and the small gap between them (so moving from the kitten down to the pill still works), instead of the
current 0.6 s grace. Never hide while recording or typing.

## Verification
Add or update `DebugHooks` so the lead can screenshot: the panel open (light/dark, with and without a missing
permission), the menu-bar icon, the kitten at each screen edge after a drag, and the X-close mid-animation. The old
`panel` hook never opened the MenuBarExtra panel on the Mac (probably a hidden `MenuBarExtraWindow` whose `isVisible`
reads true, so `guard !panelIsVisible` returns early); make the hook reliable. Put the exact hook commands and the
build/test commands under `## Mac requests`.

No Tinker, no API spend.
