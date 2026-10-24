# Brain lane digest, pass 43 (2026-10-24T22Z)

Heads: main 3772f7c (merged comms-2, clock-timers, planner-demos, planner-retrieval k=1 default via serve_brain.sh, mascot-animal),
wip/local 8fcf55f (ml/src identical to main), cloud/decisions f6fb133 (lazy mlx import, brain-34 unchanged).

Counts (open): P0 1 / P1 10 / P2 10.

Tests on Linux (mlx stubbed): product suite 699 passed / 2 skipped without stub (22 modules need mlx to collect).
Review repros on main 3772f7c: 43 failed / 27 passed (6 new in test_brain_pass43.py; 2 brain-13 tests are stale, finding resolved).
Every previously open finding with a repro still fails on main 3772f7c; comms-2 merge carries brain-38 onto main.

## Open P0/P1 (ranked)
1. brain-39 P0 Restart/shut down/log out/empty scripts run without CONFIRM — ml/src/brain/orchestrator.py
2. brain-38 P1 Deterministic message parser hijacks non-messaging commands (now on main) — ml/src/brain/comms.py
3. brain-40 P1 Final utterance reuses ARGS from the uncased, unpunctuated partial — ml/src/brain/orchestrator.py
4. brain-35 P1 Permission-prompt gate checks the pre-batch observation — ml/src/brain/orchestrator.py
5. brain-24 P1 Fuzzy destructive path lookup picks a different existing file — ml/src/brain/orchestrator.py
6. brain-25 P1 Calculator delivery can type into the wrong frontmost app — ml/src/brain/orchestrator.py
7. brain-30 P1 35B escalation load races — ml/src/brain/orchestrator.py
8. brain-29 P1 open_app/site rewrite opens website for installed Zoom/Teams/Outlook — ml/src/brain/orchestrator.py
9. brain-16 P1 abs_level misreads times/durations/percentages — ml/src/brain/orchestrator.py
10. brain-17 P1 Compound check runs serial route passes before speculative reuse — ml/src/brain/orchestrator.py
11. brain-22 P1 Planner history format conflict — ml/src/brain/plan_bank.py

## Highest-leverage next moves
- brain-39: OR the module-level _DANGEROUS_SCRIPT into the method before the read-verb allow-list (one line).
- brain-40: only reuse spec ARGS for non-free-text skills, or recase from the final transcript.
- brain-38: gate comms parser behind router top == send_message before demo.
