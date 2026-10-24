# training lane digest — pass 28 (main 04c3930, wip/local aec8fbf, cloud/data-pipeline 9b36081, cloud/decisions 6d395df)

Open: 1 P0, 10 P1, 12 P2. Pass 28: no new findings. main merged pitch-3 (router acc quoted on route_v1_clean only, training-37 now on main) and grounder-wire (planner, not lane). route_v1_clean_both == route_v1_clean (103 rows, byte-identical): it2 data adds no near-duplicates. it2 still blocked by training-29.

## Open P0/P1 (ranked)
1. **training-23 (P0, main)** — default router r2 is a re-export of main-final, trained on stale pre-fix route data; tau .45 fitted on its stale val. evalcheck: its train data touches 37/140 route_v1 and 10/43 live_t1 cases.
2. **training-37 (P1, main)** — route_v1_clean (103) drops mostly short commands (<=3 words: 51% of dropped, 3% of clean); not comparable with route_v1 or short-command benchmarks.
3. **training-29 (P1, data-pipeline)** — short_edit1 now 'either side short' and a hard abort gate in train.py; mostly spurious matches drop core short commands.
4. **training-32 (P1, cloud/decisions)** — >=30% route replay still unimplemented; H6 judged on route_v1.
5. **training-5 (P1)** — Tinker spenders with per-run guards; billing lags.
6. **training-26 / training-28 (P1, data-pipeline)** — pronoun ASK relabeled concrete; media_control in Premiere.
7. **training-24 / training-25 (P1)** — ASK undercoverage; weak labels media_control/dark_mode/find_file.
8. **training-8 / training-15 (P1, data-pipeline)** — no 15% adjudication STOP; teacher subset skew.

## Next moves (max 5)
1. Fix short_edit1 (near-variant/stopword substitutions only, skip 1-token), then rebuild route_v1_clean and re-run evalcheck.
2. Fix pronoun ASK and media_control contexts; launch it2 from route_train with pinned split (~$29), answer-only ARGS, untied export, H9 gate.
3. Quote router accuracy as full route_v1 + clean subset with length buckets; treat r2's route_v1 ARGS 1.000 as contaminated until the evalcheck is clean.
4. Decisions joint run: replay from post-fix route_train only, judge H6 on route_val.
5. One shared cumulative ledger for Tinker (and the decisions API budget).
