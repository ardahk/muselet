# Brain lane digest — pass 71 (2026-10-25T05:35Z)

Open: **P0 0 / P1 9 / P2 16**. New: brain-53 (wip/local).

## Branches
- **main e425cad**: unchanged since pass 70.
- **wip/local 323d274**: snapshot on main@c711320 (= origin/mac/blind-planner, 2 commits ahead of main). Blind planner work:
  - `--planner-blind base` (default): blind tasks (fallback, page task, open-ended redirect, or any blind observation) plan with the base 4B + few-shot + retrieval k=1 + think 512 every turn. Weights are shared via the memoized load, so no extra 4B in memory. Once blind, it also overrides the opt-in escalation planner.
  - Blind tasks run at most 2 actions per turn; the rest of the decode is not cancelled (latency only).
  - `Finish when:` end-state line from new finish.py on every planner turn -> brain-53.
  - App-only `expect app "X"` no longer counts as done evidence unless the goal is a bare open. Looks right.
  - Screen text is dropped when an IDE/terminal is frontmost. Looks right.

## New
- **brain-53 (P2, wip/local)**: finish_when picks one regex for the whole goal: "open the email from john and reply yes" -> "... is frontmost"; "find a recipe and email it to mom" -> "a results page ..."; "start a 5 minute timer" -> "... is frontmost"; "navigate to settings" -> "a route to settings". Added to every planner turn, LoRA included (untrained input, as brain-22). Repro tests/test_brain_pass71.py: 5/5 fail on wip/local, skipped on main.

## Rechecks
- All open findings unchanged on main.

## Tests (MLX stub, Linux)
- wip/local: 20 failed = 18 MLX-only + 2 test_grounder_wire blind-hint cases (NameError: test uses `orchestrator.BLIND_HINT` without importing it). 2332 passed.
- Review repros on wip/local: 35 failed / 54 passed (same as main) + pass71 5/5 fail.
