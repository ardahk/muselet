# decisions — digest (pass 73)

Heads: main 85958b0 (soft expects whenever a finish criterion exists (a524768), which widens -41; new -46 P2: cart done accepts a pre-existing '1 item'; shopping few-shot affects base/35B prefix only; -37 P0, -38/-40/-41/-43 P1 live), wip 3d21638 (= main), cool-tasks 3937e6b (main merge). Counts: 1 P0, 14 P1, 14 P2. Budget: about $142.06 MTD estimated.
Contamination re-check this pass: 2400 freshly generated code-family items vs JevBench public (231, pinned 609a664) + TD test (pinned 80cb93a): 0 word-13-gram hits. Authored rows / HF v1 data not re-checkable (private, HTTP 401).

## Open P0/P1 (ranked)
1. decisions-37 P0 LIVE on main: inline() lacks temperature attrs -> planner done-verifier always errors (incl. 35B escalate blind planner), verify silently off — ml/src/brain/generic_decide.py:177-190@e9fb42d
2. decisions-40 P1 open_ended_redirect overrides correct routes (route_v1_clean 4/103, route_v2 64/955 with gold labels) LIVE on main (now 3/103, 46/955) — ml/src/brain/orchestrator.py:1502-1508@e425cad
3. decisions-41 P1 LIVE on main: finish-evidence 'search' done accepted from the planner's own URL (_last_ok_url) and a mis-cut subject; bypasses expect + model verify — ml/src/brain/finish.py:112@e2f7e5e
4. decisions-43 P1 LIVE on main default-on agentic apps redirect all app-kind routes to the planner: 22/103 route_v1_clean, 290/955 route_v2; route/e2e claims no longer describe the shipped path — orchestrator.py:1655@1904638
5. decisions-38 P1 route claims fixed by #68 except claims.md:200 'default tau 0.55' — pitch/claims.md
6. decisions-32 P1 Full run fails its gate; TD +.0065 vs DeskMind is within noise, test-selected — training/decisions/HANDOFF.md:7-8,82-89
7. decisions-5 P1 4-bit MLX export has no logit parity check vs Tinker; Tinker numbers can't be carried over — training/decisions/export.py
8. decisions-33 P1 near_miss_values makes gold the medoid (~2x chance) — training/decisions/families/core.py:29-49
9. decisions-17 P1 per-family noul priors (counting 7.5% true, numeric 73%) — families/*
10. decisions-14 P1 live_t1 T1 quoted while live_t1 was the tuning set — pitch/claims.md
11. decisions-13 P1 route_acc 'top-1' is tau-gated — pitch/claims.md:13
12. decisions-25 / -4 / -3 P1 data brief stale; noul order flip; route regression unmeasured

## Highest-leverage next moves
- NOW: set temperature_probs/conf = 1.0 in GenericMLXDecider.inline() on main (decisions-37, P0); add a __new__-path unit test.
- Fix decisions-41 on main (drop _last_ok_url as search evidence, fix _subject cuts); agentic-apps is on main: run e2e AGENTIC_APPS=0 vs 1 and planner-LoRA parity/bench with hidden_skills (decisions-43, -42).
- Pin BLIND_PLANNER and decide LoRA vs 35B for app tasks; make docs-final match the merged code and log the planner per trace (decisions-44, -45). On main: pass goal= in _finish_evidence; play/search evidence must use the observed url only, require the subject in the title, and reject loading/404 (-41); with soft expects it is the done gate.
- Quote {{route_acc}} for it3 @ .50 (serving) and fix claims.md:13,163 / REPORT.md:12 (decisions-38).
- Bench the mlx4 export on the Mac with the same runners before quoting any number (decisions-5); results.md: label the full run below DeskMind on JevBench, TD tie on a different backend, test-selected (decisions-32).
