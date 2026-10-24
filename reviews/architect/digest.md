# architect digest - pass 46 (2026-10-24T22:10Z)
Reviewed: main 3772f7c, wip/local 8fcf55f (tree = main), every cloud/* head (handoff notes, decisions f6fb133, data-decisions 91de461, data-pipeline 830ba35).
New: main ships planner retrieval k=1 (plan_bank.py) plus comms parser and clock-timers. cloud/* now holds cut-over handoff notes only. Tinker is at $136/$150, so no new training. Re-checked open findings: 8, 13, 24, 15, 16, 20 and 23 are still open (no goal check, no committed parity JSON, cli --model-name still 'muselet' on decisions/data-decisions with the tinker backend, it3 not served).

## Open P1 (ranked)
1. architect-29 P1 - No competitor benchmark number exists with 11 h left - pitch/claims.md
2. architect-27 P1 - premiere_command sends shortcuts without Timeline focus, always reports success - app/Sources/HandsKit/Skills.swift
3. architect-24 P1 - No generic goal-level done check - docs/REPORT.md / planner done path
4. architect-28 P1 - Retrieval bank holds paraphrases of v2-holdout goals; ship gate inflated - ml/src/brain/plan_bank.py
5. architect-26 P1 - Planner prompt teaches cmd+t as Premiere default transition - prompts/planner_system.md
6. architect-13 P1 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
7. architect-8 P1 - No Mac parity result for it2 - evals/router_check.py
(P2: architect-30 first action waits for line 2; 23, 20, 15, 16)

## Highest-leverage next moves
1. Run the HobbyLM r4 replay (it2, strict), then DeskMind Bench. These are the only route to a measured "beats competitor" claim. ~1.5 h live.
2. Re-run the decisions calibrated JevBench + TD eval (~1 h, ~$0.3). If it is >= .831 / .658, that is the System One win; otherwise say "DeskMind leads" in the pitch.
3. Demo hardening for Premiere: shift+3 before shortcuts, fix cmd+t to cmd+d in the prompt, and rehearse 2:00-2:30 twice. ~20 min.
4. Rebuild the retrieval bank with a paraphrase deny (Jaccard >= .5 vs holdouts) and re-run the k=0/1 v2-holdout gate before quoting +7.2. ~30 min.
5. Flush the first planner action once line 2 is known not to be `expect`: ~0.2-0.3 s per planner turn. ~45 min.
