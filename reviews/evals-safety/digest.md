# evals-safety digest, pass 7 (self-poll, 2026-10-24T06:49:41Z)
## Open P0/P1 (ranked)
1. evals-safety-2 P0: script confirm bypassable via System Events click, Safari do JavaScript/open location, and raw «event» (ml/src/brain/orchestrator.py, now on main)
2. evals-safety-18 P1: pitch claims confirm/verify guarantees the code does not provide (pitch/claims.md)
3. evals-safety-14 P1: bool 'on' regex override inverts mute (ml/src/brain/orchestrator.py)
4. evals-safety-15 P1: evals/external 'text' key crashes decontam/dedup (training/src/muselet_train/decontam.py)
5. evals-safety-16 P1: HobbyLM frozen task files gitignored (.gitignore)
6. evals-safety-11 P1: done is not final-state verified (ml/src/brain/orchestrator.py)
7. evals-safety-6 P1: System Events clicks and non-Apple chat apps skip confirm (ml/src/brain/orchestrator.py)
8. evals-safety-10 P1: HobbyLM decontam path not asserted (training/src/muselet_train/decontam.py)
9. evals-safety-4 P1: 'no' string is truthy, so ctx online renders as yes (ml/src/brain/decision.py)
10. evals-safety-19 P1: HobbyLM rerun scored by its own 'completed', Muselet by strict final state (bench/hobbylm/replay.py)
Resolved this pass: -13 (weekend key on finance-2).
Checked and clean: finance-2 f4ae461 recomputed (totals, categories, dups and duplicate_status, outlier, refund, weekend 32 rows; receipts 02/04/05 now use OCR-style names and a 1-day posting delay, and their gold rows 12/56/60 match the amounts); regeneration byte-identical 13/13; 144 finance tests pass. live_t1 grades by final state, with a false-done metric and restore steps.
New P2: -20, grounding --limit takes the first N samples, so it covers one app (bench/grounding/run_screenspot.py).

Pass 7 checked, no new findings: cloud/brain-2 9f41c11 (calc.py spot-checked on 19 queries, all correct or None; slot-fill execution still goes through execute_actions and its risk confirm; the brief doesn't touch -2/-11/-14). cloud/data-pipeline 8f0b9bc (Phase-1 trainer aborts above --max-usd before the run; pilot val top1 0.88 is an in-distribution synthetic split, not route_v1, so don't quote it as router accuracy).

## Highest-leverage next moves
- Remove System Events from the script read allowlist and block `click|do JavaScript|open location|«event`.
- Fix the pitch claims rows, or fix -2/-11, before recording the video.
- Limit the `on` override to wifi/bluetooth/dark_mode.
- Before merging cloud/bench: un-ignore bench/hobbylm/upstream/data, and read `text` or `utterance` in decontam/dedup.
- Score the HobbyLM rerun and Muselet with the same final-state grader before quoting the comparison.
