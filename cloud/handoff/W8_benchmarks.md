# W8: Benchmarks: live suite, HobbyLM r4, DeskMind Bench, report numbers (Mac only)

Repo `ardahk/muselet`. Read `bench/RUNBOOK.md` (exact commands), `bench/live/README.md`, `docs/HANDOFF.md` §8, and
the LIVE-TEST SAFETY part of `AGENTS.md`. **Every live case runs through a runner; nothing is driven by hand.**

## State
- **Live suite** `evals/live_t1.jsonl`: 43 cases.
  - Manual (excluded): wifi-off, bt-off, lock, ask-text, confirm-no-send. The comms cases wait for a
    pronoun/test-contact strategy.
  - Morning run: T1 19/22, T2 1/5.
  - Since then: grader fixes (finance/advisor final-state checks, the Finder `is list view` check, the
    file-trash guard allowance, a widened degree range) and Finder no-user-windows preconditions.
  - A second run (block 2) is in flight; results go to `/tmp/bench_block2_report.md` and `runs/bench/live/<ts>/`.
- **HobbyLM r4 sealed** (125 live tasks: event 30, calc 30, none 16, device 15, app 10, timer 8, folder 6, dark 6,
  screenshot 4).
  - The Muselet run (block 2) is in flight: `bench/hobbylm/replay.py --system muselet --round r4 --repeats 1
    --external-brain --port 8766`.
  - HobbyLM's published score is **90/125 (72%)**, from their card and their grader.
  - The same-Mac rerun of HobbyLM (`--system hobbylm --hobby-home ../bench-ext/hobby-mac`) is optional. Do it
    only if Muselet's strict score doesn't clearly beat 90/125, because our strict final-state grading is
    harsher than their "completed" (review finding evals-safety-19).
- **DeskMind Bench diag-v27** (13 tasks × 3), not run yet.
  - Tasks are in Simplified Chinese; their reference runs used a zh-Hans locale.
  - **Plan without logging out:**
    1. Save the current value: `defaults read -g AppleLanguages > /tmp/applelanguages.bak`.
    2. `defaults write -g AppleLanguages -array zh-Hans en-US`.
    3. Relaunch only the apps the diag tasks use. Most start in Finder: `killall Finder`, which relaunches
       itself.
    4. Run per `bench/RUNBOOK.md` §6 (6a/6b DeskMind brain-0.8b/4b, 6c Muselet shim, 6d Muselet's own loop,
       6e regrade).
    5. Restore the saved AppleLanguages and relaunch Finder.
  - Disclose "global AppleLanguages zh-Hans, apps relaunched, no logout" in the report.
  - Only with a router whose DeskMind overlap is 0 (it2 or later).
  - The user approved the locale switch.
- **System One** (JevBench / typed-decisions) are model-only: RUNBOOK §3.

## Rules
- Run only while the user is away and has said OK. The screen must be unlocked; use `caffeinate -dimsu`. Results
  gathered on a locked screen are invalid.
- Close or skip document apps. The runner skips cases when user documents are open, and those skips must be
  reported with counts.
- Event tasks only run in the local "Muselet Bench" calendar (default calendar), checked with
  `python -m bench.hobbylm.calendar_safety probe`.
- `harness_timeout` rows must be rerun before quoting a score.
- One main brain + one benchmark brain at most. Kill the benchmark brain after its run.

## Report
Per run:
- the command and run dir;
- executed / skipped (by reason) / harness_timeout counts;
- strict pass by tier/category/kind;
- false_done;
- first-action + verified latency p50/p95.

For each failure: the RPC sequence and the failing check. Then update `docs/REPORT.md` and `pitch/claims.md`
with sources (W10).
