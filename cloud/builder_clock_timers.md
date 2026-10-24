# Cloud builder: clock-timers, timers in the macOS Clock app — Muselet (Swift + Python)

Repo `ardahk/muselet`. Read `AGENTS.md` and `docs/native_vs_muselet.md` (the lead approved option A: Shortcuts
CLI). Branch `cloud/clock-timers` from main, one PR. You can't compile Swift on Linux. Write carefully against the
existing HandsKit APIs (`app/Sources/HandsKit/Timers.swift`, `Skills.swift`, `RPC.swift`); the lead's team
compiles and tests on the Mac.

## User requirement
"I prefer the timer to be set in the Clock app on the Mac, rather than Muselet's interface." Today `start_timer` is
an internal Muselet timer: HandsKit `Timers.swift` plus the `timers` / `timers_cancel` RPCs.

## Design (settled)
1. **One-time setup by the user.** A shortcut can't be installed silently.
   - The user creates (or imports) a shortcut named exactly `Muselet Start Timer`:
     Receive Text input → Get Numbers from Input → Start Timer for (Numbers) seconds.
   - Optional: `Muselet Cancel Timer` (Cancel Timer) and `Muselet Timer Status` (Get Current Timer → Stop and
     Output).
   - Write the click-by-click steps for macOS 27 Shortcuts to `docs/CLOCK_TIMERS.md`, so the lead can hand
     them to the user. Mark them "unverified on macOS 27" where you're not sure of an action's name.
2. **HandsKit `start_timer` skill (Swift).**
   - If `Muselet Start Timer` exists, run `/usr/bin/shortcuts run "Muselet Start Timer"` with the duration
     in seconds as input:
     - pass the input via `--input-path` to a temp file holding the number, or via stdin;
     - use Process with a 10 s timeout;
     - no shell, and no AppleScript `do shell script`. Then return
       `{backend:"clock", seconds, label, ms}`.
   - Detect the shortcut with `shortcuts list`, cached for 60 s and refreshed on a miss. Expose that through
     `hands probe timers` and a new `timer_backend {}` RPC -> `{clock_ready: bool, shortcuts: [names]}`.
   - If the shortcut is missing or the run fails (non-zero exit, timeout), fall back to today's internal timer
     and return `{backend:"muselet", fallback_reason}`.
   - Keep the internal timer code. It is the fallback and stays selectable: Settings toggle
     "Use the Clock app for timers", default on when the shortcut exists.
   - `timers_cancel` with backend clock runs `Muselet Cancel Timer` if present, else reports `unsupported`.
     `timers` merges Muselet's own record of the timers it started (label, fires_at) with the backend.
3. **Brain (Python).**
   - `start_timer` replies "Timer set in Clock for 10 minutes" or "Timer set for 10 minutes" (fallback); 12
     words or fewer.
   - When the fallback happens because the shortcut is missing, add once per brain session: "Add the Clock
     shortcut in Settings to use the Clock app".
   - Durations stay parsed by code (existing `parse_duration`).
4. **App Settings.** Add a Timers row:
   - status (Clock ready / Shortcut missing);
   - a "Set up" button that opens `docs/CLOCK_TIMERS.md` steps in the panel, or opens Shortcuts.app via
     `NSWorkspace.open(URL(string:"shortcuts://")!)`;
   - the toggle.

## Tests
- Swift pure-logic tests: shortcut-name detection from `shortcuts list` output; input file content; fallback
  decisions on exit codes and timeouts; the `timers` merge.
- Python tests for the bubbles and the once-per-session hint.
- Don't break the existing timer tests or the HobbyLM timer grading. `bench/hobbylm` reads Muselet's own timer
  snapshot, so keep writing it on both backends.

Report in the PR body: files changed, test counts, and exactly what the lead must verify on the Mac (the shortcut
steps, `shortcuts run` latency, Clock showing the timer).
