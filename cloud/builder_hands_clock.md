# Lane: hands-clock — start timers by driving the Clock app directly (AX), Clock in front

The user wants timers in the Clock app, with Clock brought in front so they see it, and no Shortcuts setup.
Branch `cloud/hands-clock` from `main`, one PR. Swift (uncompiled here; the lead compiles and tests on the Mac) plus
small Python changes. Read `docs/CLOCK_TIMERS.md`, `docs/native_vs_muselet.md` §1 and the existing Clock backend in
`app/Sources/HandsKit` (`Skills.swift`, the clock/shortcuts code from PR #34, `Timers.swift`).

## What Clock exposes (lead, observed on the Mac, macOS 27, `hands observe --app Clock --scope app`)
```
app: Clock | window: "Clock"
#4 popup "Add"
#5 radio "World Clock" unchecked
#6 radio "Alarms" unchecked
#7 radio "Stopwatch" unchecked
#8 radio "Timers" checked
#9 textfield "Timer" value=""
#10 popup "Radial (Default)"
#11 button "Cancel" disabled
#12 button "Start"
#13 slider "slider"
#14 slider "slider"
#15 slider "slider"
```
The three sliders are presumably the hours / minutes / seconds wheels (order them by frame x). Unknown: their value
ranges, whether `AXValue` is settable, which actions they support, and what a running timer looks like in the tree.

## Build
1. **`hands probe clock`** (read-only): dump the Timers tab elements with role, label, value, min/max, frame,
   settable attributes and supported actions; also the tree while a timer runs, if one is running. The lead runs this
   first, so make it robust.
2. **Clock AX backend** for `start_timer`: launch/activate Clock (it ends frontmost), select the "Timers" radio,
   set the three wheels (set `AXValue` if settable, else `AXIncrement`/`AXDecrement` until the read-back matches),
   set the "Timer" label field when a label is given, press "Start", then verify by re-observing (Start replaced by
   Pause/Cancel enabled, or a running-timer element). Each step checks its result; any failure falls back.
   Return `{backend: "clock_ax", seconds, label, ms, verified, fires_at, timer_id}`.
3. **Backend order:** `clock_ax` → the existing Clock shortcut (if installed) → Muselet's internal timer, with
   `fallback_reason`. Keep the Settings › Timers "Use the Clock app" toggle; the shortcut becomes optional.
   `timer_backend` reports `clock_ax_ready`.
4. **Cancel / list:** read running timers from the Timers tab where possible and keep Muselet's own records (bench
   snapshots and `hands probe timers` must keep working). Cancel presses that timer's cancel control if it is found,
   else returns `unsupported` as today.
5. **Brain:** the delayed shortcut-setup hint in `orchestrator.py` must not fire when `clock_ax` worked; the reply
   stays short ("Timer set for 10 minutes").
6. Update `docs/CLOCK_TIMERS.md` and the RPC lines in `AGENTS.md`.

Tests: Swift unit tests with a fake AX layer if the existing HandsKit tests have that pattern (look first), and
Python tests for the hint logic. No Tinker, no API spend.
