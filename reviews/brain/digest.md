# Brain lane digest, pass 45 (2026-10-24T22:3xZ)

Heads: main ebdd639 / wip/local eb1d232 (no ml change), cloud/w9-safety 2a7d0df (+ escalation serialize, installed-app
preference, pathfind; reverted "done requires verified evidence"), cloud/memory = memory-lt 5cd44e6 (working memory +
follow-up rewrite), cloud/router-it3-serve b455d2c (MUSELET_ROUTE_CATALOG v3; only diff vs v2 is compose_text.target
enum->string, handled in compose_text.py), cloud/planner-lora ceafe3d (prompt_tokens refactor, behavior-preserving).

Counts (open): P0 1 / P1 11 / P2 10. On w9-safety: brain-39, 14, 24, 25, 29, 30 all pass; merging it closes 1 P0 + 4 P1 + 1 P2.
Tests (mlx stubbed): w9 1567 passed / 8 stub-only; memory 1467 passed / 9 stub-only; memory adds no review-repro failures.
Memory note (unverified risk, outside lane): bench/hobbylm/muselet_brain.py keeps one Orchestrator for the whole replay and
memory TTL is 600 s, so pronoun/again follow-ups in one case can resolve against the previous case.

## Open P0/P1 (ranked)
1. brain-39 P0 Restart/shut down/log out/empty scripts run without CONFIRM (fixed on w9-safety) - ml/src/brain/orchestrator.py
2. brain-41 P1 ARGS decode cap of 24 tokens silently truncates free-text values - ml/src/brain/decision.py
3. brain-38 P1 Deterministic message parser hijacks non-messaging commands - ml/src/brain/comms.py
4. brain-40 P1 Final utterance reuses ARGS from uncased, unpunctuated partial - ml/src/brain/orchestrator.py
5. brain-35 P1 Permission-prompt gate checks the pre-batch observation - ml/src/brain/orchestrator.py
6. brain-24 P1 Fuzzy destructive path lookup picks a different file (fixed on w9-safety) - ml/src/brain/orchestrator.py
7. brain-25 P1 Calculator delivery can type into wrong app (fixed on w9-safety) - ml/src/brain/orchestrator.py
8. brain-30 P1 35B escalation load races (fixed on w9-safety) - ml/src/brain/orchestrator.py
9. brain-29 P1 open_app site rewrite for installed Zoom/Teams/Outlook (fixed on w9-safety) - ml/src/brain/orchestrator.py
10. brain-16 P1 abs_level misreads times/durations/percentages - ml/src/brain/orchestrator.py
11. brain-17 P1 Compound check serial route passes before spec reuse - ml/src/brain/orchestrator.py
12. brain-22 P1 Planner history format conflict - ml/src/brain/plan_bank.py

## Highest-leverage next moves
- Merge cloud/w9-safety (closes brain-39 P0 and four P1s).
- brain-41: per-skill ARGS budget (~96 for string args) + truncated flag -> ASK.
- brain-40: rerun ARGS on the final transcript for free-text skills.
- Before merging cloud/memory: reset WorkingMemory per bench case (or on hello) so benchmark cases cannot leak into each other.
