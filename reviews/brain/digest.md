# Brain lane review: pass 77 (2026-10-25T07:10Z)

Open: P0 0, P1 13, P2 22. New: brain-63, brain-64.

## Branches
- main 3a0860c: 35B blind planner (`--planner-blind escalate`), auto-picked by serve_brain.sh when cached (brain-64). Symlink untracking is outside the lane.
- wip/local 83cf584: snapshot on main; lane identical.
- cloud/agentic-evidence 1918cad: play and timer-start auto-done from the goal (brain-60 wider); stale test double fixed.
- cloud/app-knowhow c69dfec: test-only lane change; no finding.
- cloud/browser-flow 485763f: merged main (brain-57/58 now apply); web UI guard (brain-63).

## New
- brain-63 (P2, browser-flow): the guard refuses result links with a query string on the current site (youtube watch?v=, amazon /dp/...?th=1). Repro: tests/test_brain_pass77.py.
- brain-64 (P2, main, code reading): the blind planner becomes the 35B whenever it's in the HF cache. That means memory, think-512 latency and bench comparability depend on the machine.

## Rechecked
- brain-60 (P1): play auto-done now ignores the subject (any Pause button counts as done). Email To-field repro still fails.
- brain-61, brain-59, brain-62, brain-57, brain-58, brain-50, brain-54, brain-55, brain-53, brain-52, brain-47/48/49, brain-42/43, brain-22: unchanged.

## Tests
18 MLX-only suite failures on every branch (Linux). Review repros failed: main 53, agentic-evidence 56, app-knowhow 51, browser-flow 55.
