# architect digest - pass 48 (2026-10-24T22:40Z)
Reviewed: main ebdd639 (briefs planner-think/verify, hands-clock, live-cases, docs-demo; AGENTS now allows planner step p50 <= 3 s), wip/local eb1d232, cloud/planner-lora ceafe3d, router-it3-serve b455d2c, memory/memory-lt 5cd44e6, ui-polish e8bceef (Swift UI only, statically reviewed), docs-demo 095d4ef, w9-safety 2a7d0df.
New: planner-lora 2 epochs ($5.84 est; step 72 picked on dev .983 vs base .695). The dev split is the same teacher generators, so it doesn't predict holdout; the Mac holdout gate (>= .672) is still to run. it3 serving is opt-in with catalog v3 (architect-23 fix pending merge). Memory runs a rule resolver per utterance, with a <= 40-token LLM rewrite only for suspected follow-ups. docs-demo quotes retrieval k=1 held-out numbers (see architect-28) and leaves competitor rows as TBD. No new findings this pass.

## Open P1 (ranked)
1. architect-29 P1 - No competitor benchmark number exists - pitch/claims.md
2. architect-27 P1 - premiere_command sends shortcuts without Timeline focus, always reports success - app/Sources/HandsKit/Skills.swift
3. architect-24 P1 - No generic goal-level done check - planner done path (planner-verify brief now targets it)
4. architect-28 P1 - Retrieval bank / demo gate pass paraphrases of holdout goals - ml/src/brain/plan_bank.py
5. architect-26 P1 - Planner prompt teaches cmd+t as Premiere default transition - prompts/planner_system.md
6. architect-13 P1 - System One tinker backend reports as 'muselet' - bench/systemone/cli.py
7. architect-8 P1 - No Mac parity result for it2 - evals/router_check.py
(P2: 31 read-only Numbers scripts confirm; 30 first action waits for line 2; 23 it3 catalog, fix on router-it3-serve; 20, 15, 16)

## Highest-leverage next moves
1. Run HobbyLM r4 (it2, strict), then DeskMind diag on the Mac. These are the only route to a measured competitor claim. ~1.5 h.
2. Run the Mac matrix for planner-lora (k=0/1 vs shipped) on v1-ho/v1-ho2/v2-ho. Paraphrase-dedupe the holdouts first, or report the 15 overlapping v2-holdout items separately. ~45 min.
3. Re-run the decisions calibrated JevBench + TD eval (~$0.3) inside the remaining ~$5.
4. Premiere hardening: shift+3 before shortcuts, cmd+d in the prompt, rehearse 2:00-2:30. ~20 min.
5. Merge router-it3-serve only after the val tau fit and route_v1_clean/ARGS ship rule pass; keep it2 as the default until then.
