# Lane: live-cases — multi-turn live cases for the new capabilities (memory, Clock, again/undo, Notes)

Tonight's live run is our main valid measurement, and it doesn't cover the new capabilities yet. Branch
`cloud/live-cases` from `main`, one PR. Read `bench/live/run_live.py`, `bench/RUNBOOK.md`, `evals/live_t1.jsonl`
(case schema: `setup`, `restore`, `check`, `precondition`, `confirm_reply`, `tier`, teardown rules) and the live-test
safety rules in `AGENTS.md`. Python only. You can't run it here (no Mac); the lead runs it.

## 1. Harness: multi-utterance cases (additive; existing cases must behave byte-identically)
- New optional field `"turns": [{"utterance": "...", "confirm_reply": null|true|false, "check": [...]?,
  "wait_s": 1.0?}, ...]` used instead of `utterance`. Turns are sent in order to the same brain session (same
  WebSocket, so the brain's working memory carries over), each waiting for that turn's final outcome before the
  next. Per-turn `check`s are optional; the case's top-level `check` grades the final state. Record per-turn
  outcome, latency and the brain's reply in the results.
- Preconditions, document inventory, setup, restore and teardown work exactly as for single-turn cases.
- `--dry-run` lists the turns. Unit tests in `bench/tests` with the existing fakes.

## 2. New cases in `evals/live_t2_new.jsonl` (separate file; don't edit `evals/live_t1.jsonl`)
Each with mechanical preconditions, setup/restore, final-state checks, and teardown that closes only what the case
created:
1. `mem-wiki-search`: "navigate to wikipedia" → "search for history". Check: the browser tab the case opened has a
   URL containing `wikipedia.org` and `history` (read through AX of the browser address bar / web area, no Apple
   Events to the browser).
2. `mem-again-volume`: setup volume 30; "turn the volume up a bit" → "again". Check: volume ≥ the level after turn 1
   + 5. Restore the volume.
3. `mem-undo-darkmode`: record the appearance; "turn on dark mode" → "undo that". Check: appearance equals the
   recorded original. Restore it.
4. `clock-timer-front`: "set a timer for 2 minutes". Check: Clock is frontmost and a 2-minute timer is running
   (`hands probe timers`, backend `clock_ax` or `clock`); teardown cancels that timer. Precondition: no timer
   already running in Clock.
5. `notes-template`: "open notes and write a template about my day so I can fill it out". Check: a note created
   during the case exists with ≥ 4 non-empty lines (read through System Events / AX, no Apple Events to Notes
   beyond what existing cases use); teardown deletes only that note.
6. `mem-followup-app`: "open finder" → "go to my downloads". Check: the front Finder window shows
   `/Users/<user>/Downloads`; teardown closes only that window.
Mark them tier `T2`, category `memory` / `timers` / `notes`.

## 3. RUNBOOK
Add the exact commands for running only these cases and the whole suite.

No Tinker, no API spend.
