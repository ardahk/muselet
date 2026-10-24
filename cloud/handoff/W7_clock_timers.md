# W7: Timers in the macOS Clock app

Repo `ardahk/muselet`. Read `docs/native_vs_muselet.md` (research; option A approved) and
`cloud/builder_clock_timers.md` (the full spec).

## State
- **Today:** `start_timer` is Muselet's internal timer (HandsKit `Timers.swift`).
- **In flight:** `cloud/clock-timers` implements:
  - `start_timer` through `/usr/bin/shortcuts run "Muselet Start Timer"`, with the seconds as input;
  - `timer_backend {}`;
  - a Settings row;
  - the internal timer as the fallback;
  - `docs/CLOCK_TIMERS.md`, click-by-click setup steps for the user.

## Mac steps
1. With the user, create the shortcut once (Shortcuts.app):
   - `Muselet Start Timer`: Receive Text → Get Numbers from Input → Start Timer for (Numbers) seconds.
   - Optional: `Muselet Cancel Timer`, `Muselet Timer Status`.
2. Verify with `shortcuts list | grep Muselet`, then
   `time shortcuts run "Muselet Start Timer" --input-path <(echo 10)`, and check that Clock shows the timer.
   Measure the latency.
3. Compile, test and relaunch the app. Say "set a timer for ten seconds" and check that Clock fires.
4. Keep HobbyLM timer grading working: the replay reads Muselet's own timer snapshot, which must still be
   written.

## Acceptance
- The Clock timer is set by voice, with a short "Timer set in Clock for N minutes" bubble.
- The fallback works with the shortcut missing.
- Latency is recorded in `docs/REPORT.md`.
