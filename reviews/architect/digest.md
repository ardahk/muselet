# architect digest - pass 47 (2026-10-24T22:25Z)
Reviewed: main 2a2c2a9 (briefs: planner-lora <= $7 Tinker, ui-polish; builder_common now hard-stops at $148), wip/local 4f963a7 (tree = main), cloud/memory 4b519b1 (ctx.url/window_title; AGENTS keeps them out of router ctx, and decision.py renders only app/focused/selection/online/last, so router parity holds), cloud/memory-eval c05944e (memory_followups added to all three decontam gates), cloud/w9-safety 50a3b25 (script-policy hardening plus confirm-covers-next-action, statically reviewed and exercised on v2 gold scripts). New: architect-31 (P2). Updated: 28 now also covers the planner-lora data gate; 29 reflects the $148 budget.

## Open P1 (ranked)
1. architect-29 P1 - No competitor benchmark number exists with 11 h left - pitch/claims.md
2. architect-27 P1 - premiere_command sends shortcuts without Timeline focus, always reports success - app/Sources/HandsKit/Skills.swift
3. architect-24 P1 - No generic goal-level done check - docs/REPORT.md / planner done path
4. architect-28 P1 - Retrieval bank holds paraphrases of v2-holdout goals; ship gate inflated - ml/src/brain/plan_bank.py
5. architect-26 P1 - Planner prompt teaches cmd+t as Premiere default transition - prompts/planner_system.md
6. architect-13 P1 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
7. architect-8 P1 - No Mac parity result for it2 - evals/router_check.py
(P2: architect-30 first action waits for line 2; architect-31 read-only Numbers scripts confirm; 23, 20, 15, 16)

## Highest-leverage next moves
1. Run the HobbyLM r4 replay (it2, strict), then DeskMind Bench. These are the only route to a measured "beats competitor" claim. ~1.5 h live.
2. Re-run the decisions calibrated JevBench + TD eval (~1 h, ~$0.3). If it is >= .831 / .658, that is the System One win; otherwise say "DeskMind leads" in the pitch.
3. Demo hardening for Premiere: shift+3 before shortcuts, fix cmd+t to cmd+d in the prompt, and rehearse 2:00-2:30 twice. ~20 min.
4. Add a paraphrase deny (Jaccard >= .5 vs holdouts) to plan_bank and planner_demos/gate.py before the planner-lora run spends Tinker, then re-gate k=1. ~30 min.
5. Flush the first planner action once line 2 is known not to be `expect`: ~0.2-0.3 s per planner turn. ~45 min.
