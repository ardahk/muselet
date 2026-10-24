# Brain lane digest, pass 44 (2026-10-24T22:1xZ)

Heads: main 2a2c2a9 (briefs only, no ml change), wip/local 4f963a7 (ml/src identical to main),
cloud/w9-safety 50a3b25 (script-confirm hardening + brain-14 fix), cloud/memory-eval c05944e (plan_bank denylist adds
evals/memory_followups.jsonl, correct direction), cloud/memory 4b519b1 (no lane files).

Counts (open): P0 1 / P1 11 / P2 10. brain-39 and brain-14 are fixed on cloud/w9-safety; they close when it merges.
Tests (mlx stubbed): w9-safety 1498 passed / 56 skipped / 8 failed (all need real mlx). Review repros: main unchanged plus 2 new
(test_brain_pass44.py); on w9-safety, 37 review repros fail (brain-39 x5 and brain-14 now pass).

## Open P0/P1 (ranked)
1. brain-39 P0 Restart/shut down/log out/empty scripts run without CONFIRM (fix on w9-safety) - ml/src/brain/orchestrator.py
2. brain-41 P1 ARGS decode cap of 24 tokens silently truncates free-text values - ml/src/brain/decision.py
3. brain-38 P1 Deterministic message parser hijacks non-messaging commands - ml/src/brain/comms.py
4. brain-40 P1 Final utterance reuses ARGS from uncased, unpunctuated partial - ml/src/brain/orchestrator.py
5. brain-35 P1 Permission-prompt gate checks the pre-batch observation - ml/src/brain/orchestrator.py
6. brain-24 P1 Fuzzy destructive path lookup picks a different existing file - ml/src/brain/orchestrator.py
7. brain-25 P1 Calculator delivery can type into the wrong frontmost app - ml/src/brain/orchestrator.py
8. brain-30 P1 35B escalation load races - ml/src/brain/orchestrator.py
9. brain-29 P1 open_app/site rewrite opens website for installed Zoom/Teams/Outlook - ml/src/brain/orchestrator.py
10. brain-16 P1 abs_level misreads times/durations/percentages - ml/src/brain/orchestrator.py
11. brain-17 P1 Compound check runs serial route passes before speculative reuse - ml/src/brain/orchestrator.py
12. brain-22 P1 Planner history format conflict - ml/src/brain/plan_bank.py

## Highest-leverage next moves
- Merge cloud/w9-safety (closes brain-39 P0 and brain-14).
- brain-41: per-skill ARGS budget (~96 for string args) + truncated flag -> ASK; one-line cap change plus parser check.
- brain-40: rerun ARGS on the final transcript for free-text skills (or recase from it).
- brain-38: gate the comms parser behind router top == send_message.
