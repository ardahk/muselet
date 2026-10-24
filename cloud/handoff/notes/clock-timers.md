## Handoff

_Last updated: 2026-10-24, at the org cut-over. PR #34 is merged; PR #42 (this handoff refresh) is open. Nothing is uncommitted._

**State**
- Done: the full `cloud/builder_clock_timers.md` brief is implemented and **merged into `main`** via [ardahk/muselet#34](https://github.com/ardahk/muselet/pull/34) (branch `cloud/clock-timers`, head `8d779cc`, now on `main`). The implementation commit is `d060b5a` (rebased on `main` @ `e2472e2`).
  - Swift, HandsKit: Clock backend, shortcut detection, fallback, cancel, merge, and the `timer_backend` RPC.
  - Swift, app: Settings › Timers card.
  - Python brain: per-backend replies and the once-per-session hint.
  - Docs: `docs/CLOCK_TIMERS.md` and `AGENTS.md`.
  - Tests: Swift and Python.
- In flight: nothing on the agent side. The merged code still awaits the lead's Mac team for compile + on-Mac checks. Any further work goes on a new branch off `main` (e.g. `cloud/clock-timers-fixes`), one PR per change.
- **Swift has never been compiled.** The agent ran on Linux. Python passes: `ml/` 1310 passed / 55 skipped; bench timer tests 24 passed. The repo has no CI.

- Not started:
  - Mac compile and test of the Swift;
  - on-Mac verification of the Shortcuts actions and Clock behaviour;
  - any fixes those turn up.

**Resume (commands)**
```sh
gh repo clone ardahk/muselet && cd muselet && git checkout main && git pull
# Linux, Python checks only:
cd ml && uv sync                                                     # uses ml/uv.lock
uv pip install --python .venv/bin/python "mlx-cpu==0.32.4"          # Linux only (libmlx.so)
.venv/bin/python -m pytest -q                                        # expect 1310 passed, 55 skipped
# Mac (required, never done):
cd app && swift build && swift test
.build/debug/hands probe timers                                      # backend.clock_ready true once the shortcut exists
echo 5 > /tmp/t.txt && time /usr/bin/shortcuts run "Muselet Start Timer" --input-path /tmp/t.txt
# new work:
git checkout -b cloud/clock-timers-fixes origin/main
```

**Exact next steps**
1. On a Mac: `cd app && swift build && swift test`. Fix any compile errors. The most likely spots:
   - the labeled-tuple append in `FakeShortcuts.runs` (`app/Tests/HandsKitTests/ClockTimersTests.swift`);
   - `case true?` / `case false?` in `SettingsView.timerBadge`;
   - the `var` captures in `ShortcutsCLI.exec` (`app/Sources/HandsKit/ClockTimers.swift`).
2. Follow `docs/CLOCK_TIMERS.md` on macOS 27 and replace every "*unverified on macOS 27*" marker with the real action/field names.
3. Run the lead's Mac checks, listed under "What the lead must verify on the Mac" in the PR body:
   - `shortcuts run` latency, cold and warm, against the 10 s timeout;
   - Clock shows and rings the timer;
   - fallback and hint;
   - toggle off means no `shortcuts` process;
   - HobbyLM timer grading and teardown.
4. Put any fixes from steps 1–3 on a new branch off `main` and open a new PR (#34 is merged). Never merge; the lead merges.

**Artifacts**
- Branch `cloud/clock-timers` (merged; do not reuse). Implementation commit `d060b5a`; handoff notes `3446136`, `8d779cc`. PR #34 (merged). Handoff refresh: branch `cloud/clock-timers-handoff`, [PR #42](https://github.com/ardahk/muselet/pull/42) (open, docs only).
- No HF repos, Tinker runs, checkpoints or run dirs: there was no training or eval in this lane.
- Python test env on Linux: `ml/.venv`, plus `uv pip install --python ml/.venv/bin/python "mlx-cpu==0.32.4"`. That install is needed only on Linux, where `libmlx.so` is missing. It is not committed.

**Spend so far**
- No Tinker, HF, OpenAI or Anthropic API spend; none of the provided keys were used.
- Devin time: one session, about 2 h of work. The agent can't see exact credit usage.

**Open questions for the lead**
- Is the 3 s delay acceptable for the "Add the Clock shortcut in Settings…" hint? It is delayed so it doesn't instantly replace the timer bubble, and it is dropped if a new utterance arrives first.
- Timeout risk: `shortcuts run` can time out (> 10 s) and still start the Clock timer, while Muselet also starts its own fallback timer, so two timers run. Keep this as is, or skip the fallback on timeout?
- HobbyLM teardown of a Clock timer without `Muselet Cancel Timer` reports `unsupported` and leaves the real Clock timer running. Should the bench require the cancel shortcut, or force the toggle off?

**Gotchas**
- `SystemHooks.inert` uses `NoShortcuts`, so unit tests never launch `/usr/bin/shortcuts`. Only `.live` uses `ShortcutsCLI`. A new test that needs Clock behaviour should inject `FakeShortcuts` via `hooks.shortcuts`.
- Clock timers are kept as `TimerRegistry` records with `backend:"clock"` and a no-op fire closure. They expire from the list on time but never ring in Muselet. That is how `timers` and the snapshot (`$TMPDIR/muselet-timers/<pid>.json`, read by bench/hobbylm) keep covering both backends.
- `shortcuts list` is cached for 60 s and re-listed on a miss at most every 2 s. Any failed shortcut run invalidates the cache.
- `timers` runs `Muselet Timer Status` only when a Clock record exists or `clock_status:true` is passed. This keeps HobbyLM baseline calls cheap.
- The fallback bubble wording changed from "10 min" to "10 minutes". `ml/tests/test_review_fixes.py` was updated to match.
- The Settings toggle is persisted as UserDefaults `muselet.clockTimers` (default true) and applied to `rpc.skills.clock.enabled` in `AppDelegate.wireActions`.
