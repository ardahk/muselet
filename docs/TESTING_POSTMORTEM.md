# Testing postmortem: seven failures in ten minutes (user session, 2026-10-24)

The user's first ten minutes hit seven failures that ~2 000 unit tests, the router/planner evals and
the live T1/T2 suites had all passed. None of the misses was bad luck: each failure lived in a gap
that the test design created. Regressions: `evals/replay/user_2026-10-24.jsonl` (offline, strict
xfail on `main` 4150ecb) and `evals/acceptance.jsonl` (on the Mac, graded from the screen).

## The seven failures and why nothing caught them

| # | What the user saw | Why no test caught it |
|---|---|---|
| 1 | "Timer set", Clock showed an unstarted 15:00 | `time-timer` (live T1) graded `trace_skill: start_timer`: the brain *routed* right, so it passed. `_timer_text` builds "Timer set for N" from the requested duration, never from `verified`/`running_added`. `clock-timer-front` did read Clock, but only with Clock **closed** first (idealised); the user had Clock open, a state no case ever set up. Unit fakes return `{"ok": true}` for any `skill`. |
| 2 | Wikipedia follow-up opened a new tab | `mem-wiki-search` checked the final URL only (the page loaded, so it passed) and never the tab count. Its setup required Safari and Chrome to be **quit** and the runbook assumed Safari/Chrome; no case pinned Zen (the user's default) or started from an existing tab. No test asserted `same_tab`. |
| 3 | "open text edit" -> app not found | Every eval and live case spells app names as typed ("launch textedit"). No STT-shaped variants (split words, lower case, no punctuation) anywhere; `FakeServer.apps` accepted any name, so the resolver was never exercised against an installed-app list. |
| 4 | Notes template -> raw AppleScript, a confirm, then "Script failed" | `notes-template` checks that a filled note exists, so a script that succeeded on the lead's Mac passed; it never forbade the `script` op or an unexpected confirm. Planner tests use canned batches and a fake `act` that returns `ok` for any script, so "the planner reaches for AppleScript" was invisible. |
| 5 | "Text Caleb ..." swallowed by a pending task | Every case starts from a clean brain. `test_pending_ask.py` covers a short list of leading verbs (`set`, `open`, ...); "text", "message", "email", "call" were missing, and no sequence put a pending ask/confirm *before* the next command. The live proxy answered every confirm instantly, so a pending state could never exist live. |
| 6 | Gmail (Workspace) reply went to Mail.app | Unit tests cover *opening* `mail.google.com` only; no test ran `draft_email` reply with a Gmail page in front, let alone Zen + `mail.google.com/mail/u/1/...` (Workspace). No live case had Gmail at all (it needs a signed-in account), so "falls back to Mail" was never observed. |
| 7 | "Forget Everything" in Settings did not stick | `memory_request({"op":"clear"})` was unit-tested against the SQLite store only. Working memory, learned workflows (`workflows.jsonl`) and the Settings round trip (clear -> reopen -> restart) were never checked; no live case touched Settings. |

## The patterns behind them

1. **Fakes that accept anything.** `FakeServer` returns success for every `act`/`skill` and the same
   observation for every `observe`; a test passes whatever the brain sends. Fix: `brain.replay.RecordedHands`
   answers only recorded calls (`match` must be a subset of the params) and fails on anything else.
2. **Idealised live state.** Live cases quit the target app, close browsers and start from a fresh
   brain, because that makes preconditions easy. Users have Clock open, Zen in front, a Gmail tab, and a
   question still pending. Fix: acceptance cases set up the user's state (Clock open, Zen default, a held
   confirm) and SKIP when it cannot be established.
3. **Wrong browser.** Browser checks named Safari and Chrome; the user's default is Zen, which has a
   different AX tree and tab model. Fix: Zen-default precondition, Zen URL and tab-count checks.
4. **No pending-state sequences.** Multi-turn cases existed but always answered confirms. Fix:
   `confirm_reply: "hold"` leaves a confirm open and sends the next utterance.
5. **No STT variants.** Evals are written, not spoken. Fix: acceptance and replay use STT spellings.
6. **Grading the claim, not the screen.** `trace_skill` and `trace_say` checks pass when the brain
   *says* it did something. Fix: `"grade": "screen"` cases must end with an AX / System Events / file /
   HandsKit-state check and may not use `trace_say` (enforced when the suite loads).
7. **Timeouts that hide outcomes.** A turn that never reached a terminal frame was recorded as
   `timed_out` with no state read, so "slow" and "wrong" looked the same. Fix: on timeout the runner
   still evaluates the turn and case checks (`timeout_observations`).
8. **No replay of real sessions.** Traces lacked `ctx`, the routed clause and the args skill, so a
   user's session could not be rerun. Fix: traces record them; `python -m brain.replay --from-trace`
   drafts a case, and every user report becomes a permanent regression before it is fixed.

## What changes in the process

- A user-visible failure gets a replay case first (it must fail on `main`), then the fix removes
  `fails_on_main`.
- PRs touching the brain run the acceptance suite on the Mac; the release checklist in
  `bench/RUNBOOK.md` defines "works": replay green, acceptance 2/2 from the screen on the user's setup,
  no timeouts or unexplained skips.
