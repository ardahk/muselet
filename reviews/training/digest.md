# training lane digest — pass 103 (main 32c0ad4)

Open: 1 P0, 19 P1, 19 P2. No new findings; training-62 updated (lh_train shares site and flow with 11/18 LH-v1 cases). Top: training-54, training-61, training-59.

## Ranked open P0/P1
1. training-54 P0 — argfix.py wording copied from HobbyLM sealed r4 (D04-D06 not held out). Outside the training lane.
2. training-61 P1 — deployed planner (base 4B native tools, THINK=1024, k=0) is unmeasured; planner_offline has no tools mode.
3. training-59 P1 — pre-router destructive regex refuses route_v2 empty-trash and v2-shell-rm; matches HobbyLM r3 N11.
4. training-53 P1 — deployed router is it3 with no sealed overlap report; README:37 unqualified.
5. training-55 P1 — merged prompt rewrite + k=0/no few-shot: .850/.770 no longer describe any default.
6. training-50 P1 — $0.84 vs $5.84 in REPORT:134 and claims:45; warn at $140 not $148.
7. training-58 P1 — script default still cache-dependent; no per-result planner metadata; REPORT 35B settings stale; soft expects unmeasured.
8. training-49 / 47 / 48 P1 — memory-eval tuple crash; route_v2 near-dup gaps; it3 family split leakage.
9. training-45 / 29 / 43 / 37 / 8 / 15 / 24 / 25 / 26 / 28 P1 — see findings.jsonl.

## Next moves
1. Measure the deployed planner (tools mode) on the holdouts against LoRA-DSL and 35B before the demo.
2. Run sealed competitor sets with ROUTER=it2, or commit the it3 overlap report.
3. Exempt Trash and scoped deletes from the pre-router refusal.
4. Correct $0.84 to $5.84 in REPORT and claims; set HARD_WARN to $148.
5. Split LH-v1 into tune/holdout before adopting H1-H4; add lh_v1 to evalcheck before H7 data.
