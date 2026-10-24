# evals-safety digest, pass 11 (2026-10-24T07:55:35Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-11 P1: done is not harness-verified (only the planner prompt rule plus a fresh-observe heuristic) (ml/src/brain/orchestrator.py)
2. evals-safety-6 P1: destructive-label gating only covers Messages/Mail/Slack. Web AX on main now feeds page text to the planner (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20 (grounding first-N), -21 (mem_guard kills :8766 = Premiere bridge port), -22 (dead weak script policy is the one tested; `open (POSIX file` paren bypass).
Resolved this pass: -4 (fixed since brain-2 741465c; my pass 9/10 'unchanged' notes were wrong).
Checked, nothing new in my lane: advisor-3 ca93147 (fixtures unchanged apart from DEMO.md; 126 tests pass). finance-3 31be399 (polls for the opened table; 164 tests pass). brain-3 14a3f52 compound fast path: each clause runs through _run_skill and execute_actions, so per-skill risk=confirm and label gating still apply, and brain-executor skills are excluded. cloud/bench 6e7cd09 now requires --deskmind-python and checks the pinned deskmind-hands commit. data-pipeline 0f3df7f only changes the parity export.

## Highest-leverage next moves
- Add a harness-side goal check on done before success (-11).
- Extend destructive-label gating beyond Messages/Mail/Slack to the web/Electron chat apps that web AX now exposes (Discord, Teams, WhatsApp, Gmail in Chrome) (-6).
- Delete the dead script_needs_confirm and test the real method with the bypass probes (-22).
- Move the bench brain off :8766 (-21); stratify grounding --limit (-20).
