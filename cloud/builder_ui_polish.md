# Lane: ui-polish — menu-bar panel that matches the kitten, hover dwell for the pill, smooth keyboard close

The user likes the kitten mascot "Muse" (PR #36, `docs/img/kitten_*.png`) and all its interactions. Three changes,
Swift only (uncompiled here; the lead compiles, runs and screenshots on the Mac). Branch `cloud/ui-polish` from
`main`, one PR, small commits per item.

Files: `app/Sources/MuseletApp/Panel/{PanelView,PanelComponents,SettingsView}.swift`, `App/Theme.swift`,
`Mascot/{MascotPalette,MascotView*,PillController,PillView,MascotController}.swift`, `App/DebugHooks.swift`.

## 1. Menu-bar panel that fits the kitten
- Restyle the panel (opened from the menu-bar icon) so it reads as Muse's home: the kitten palette from
  `MascotPalette` (cream, ginger, soft ink), rounded friendly shapes, generous spacing, a small kitten avatar in the
  header that reflects the current mood (reuse the mascot drawing at small scale, or a static render of it), and a
  short friendly status line. Keep the glass/vibrancy material (standing decision: HUD style = glass).
- Keep every function: the last request + reply, example prompts, connection status, gear → Settings. Settings stays
  behind the gear and keeps all its controls; restyle it consistently but keep it clear and dense.
- Light and dark mode both look right; respect Reduce Motion.

## 2. Pill (keyboard + mic) appears after a 1 s hover, not instantly
- Today `PillController.mascotHover` → `update()` shows the pill on the first hover event.
- New: show it only after the pointer has rested on the kitten for `hoverDwell = 1.0` s (a named constant). Leaving
  before that cancels it. Still show immediately while recording (push-to-talk) or typing. Hovering the pill itself
  keeps it open; the 0.6 s hide grace stays. Clicking/poking and dragging the kitten are unaffected, and the hover
  wake/ear animations on the kitten itself stay instant.
- Unit-test the dwell logic (make the scheduler injectable so tests don't sleep), following the existing Swift test
  patterns in `app/Tests`.

## 3. Keyboard close as smooth as open
- Opening the text field animates well. Closing is clunky: `endTyping()` collapses the field with no animation and,
  when the pill panel is key, orders the panel out and straight back in to return keyboard focus to the frontmost app,
  which shows as a blink/jump.
- Make every close path (submit, Esc, click-away with an empty field) mirror the open animation (same curve and
  duration), and hand keyboard focus back without a visible flicker (e.g. run the collapse first and do the focus
  hand-off after it completes, or hand off focus without ordering the panel out; explain the technique in the PR).
  The frontmost app must get keyboard focus back, as today.

## For the Mac check
Add debug hooks in `DebugHooks.swift` (same style as the existing ones) to force: pill shown via hover, typing open,
typing closing, and the panel open, so the lead can screenshot each state and record the close animation. List the
exact hook invocations in the PR body.

No Tinker, no API spend.
