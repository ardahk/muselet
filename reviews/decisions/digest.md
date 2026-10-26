# decisions — digest (pass 89)

Heads: main 32c0ad4 (unchanged), wip d714345 (local main@2f96add: LH fixture server, runner false_done/require_confirm, 32 H7 train tasks). decisions-50 sharpened: train tasks share the eval seed mailbox/catalog, and seed m7 holds the lh-mail-offsite answer that train tr-mail-04/-09 trajectories will observe. -41: the harness now counts false_done (core.py:1169). cool-tasks cfbec49 (-42 blocks). Counts: 0 P0, 14 P1, 18 P2.
Contamination re-check this pass: 2400 freshly generated code-family items vs JevBench public (231, pinned 609a664) + TD test (pinned 80cb93a): 0 word-13-gram hits. Authored rows / HF v1 data not re-checkable (private, HTTP 401).

## Open P0/P1 (ranked)
1. decisions-37 now P2 (was P0): inline() temps fixed on main@b92677f (generic_decide.py:183). Still missing: an inline/__new__ unit test and a Mac check that planner.verify returns p_yes; VERIFY_P was never fitted on the 35B.
2. decisions-40 P1 open_ended_redirect overrides correct routes (route_v1_clean 4/103, route_v2 64/955 with gold labels) LIVE on main (now 3/103, 46/955) — ml/src/brain/orchestrator.py:1502-1508@e425cad
3. decisions-41 P1 LIVE on main: finish-evidence 'search' done accepted from the planner's own URL (_last_ok_url) and a mis-cut subject; bypasses expect + model verify — ml/src/brain/finish.py:112@e2f7e5e
4. decisions-49 P1 main@32c0ad4 merged 71 files (-5559 lines) with the full pytest suite incomplete: stopped at 65% with failure markers, untriaged, no baseline — docs/REPORT.md:59@32c0ad4. (decisions-43 superseded by the user override at AGENTS.md:17; -48 down to P2: the deployed base-4B tools config k=0/no few-shot/think 1024 is unmeasured.)
5. decisions-38 P1 route claims fixed by #68 except claims.md:200 'default tau 0.55' — pitch/claims.md
6. decisions-32 P1 Full run fails its gate; TD +.0065 vs DeskMind is within noise, test-selected — training/decisions/HANDOFF.md:7-8,82-89
7. decisions-5 P1 4-bit MLX export has no logit parity check vs Tinker; Tinker numbers can't be carried over — training/decisions/export.py
8. decisions-33 P1 near_miss_values makes gold the medoid (~2x chance) — training/decisions/families/core.py:29-49
9. decisions-17 P1 per-family noul priors (counting 7.5% true, numeric 73%) — families/*
10. decisions-14 P1 live_t1 T1 quoted while live_t1 was the tuning set — pitch/claims.md
11. decisions-13 P1 route_acc 'top-1' is tau-gated — pitch/claims.md:13
12. decisions-25 / -4 / -3 P1 data brief stale; noul order flip; route regression unmeasured

## Highest-leverage next moves
- NOW: add an inline()/__new__ unit test and do a Mac run showing planner.verify p_yes != None (decisions-37); fix the play/search/cart done checks (decisions-41/-46).
- Run the full suite on main@32c0ad4 and on b00f679, diff the failure lists, and triage them before the demo (decisions-49); measure the deployed env (PLANNER=base, PLANNER_MODE=tools, RETRIEVAL_K=0, FEWSHOT=none) on planner_offline before quoting live planner numbers (decisions-48).
- Pin BLIND_PLANNER and decide LoRA vs 35B for app tasks; make docs-final match the merged code and log the planner per trace (decisions-44, -45). On main: pass goal= in _finish_evidence; play/search evidence must use the observed url only, require the subject in the title, and reject loading/404 (-41); with soft expects it is the done gate.
- Quote {{route_acc}} for it3 @ .50 (serving) and fix claims.md:13,163 / REPORT.md:12 (decisions-38).
- Bench the mlx4 export on the Mac with the same runners before quoting any number (decisions-5); results.md: label the full run below DeskMind on JevBench, TD tie on a different backend, test-selected (decisions-32).
