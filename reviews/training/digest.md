# training lane digest — pass 94 (main 2de65a9)

Open: 1 P0, 17 P1, 19 P2. No new findings. training-55 updated: wip sets planner k=0 + no few-shot + agentic-apps always on, so no quoted planner number matches the shipping config (P1 on merge). Top: training-54, training-59, training-50.

## Ranked open P0/P1
1. training-50 P1 — MTD about $142-144 (planner-lora $5.84 on top of $136.22). Thresholds still conflict ($140/$142/$146/$148), and the guard lags (tools/tinker_spend.py).
2. training-49 P1 — memory-eval gate appends 2-tuples; overlaps() raises ValueError, so route rebuild is broken (training/data_route/build.py, now on main).
3. training-47 P1 — route_v2 gate misses mid-length paraphrases; 13-gram rule can't fire on 640/955 items (evalcheck.py).
4. training-48 P1 — merge_it3cand keeps source splits; val3/tau may be inflated (router_check drops only exact it2-train rows).
5. training-45 P1 — it3 ARGS audit noise fixed only on the 1,061 sampled rows.
6. training-29 P1 — short_edit1 over-drops short commands.
7. training-43 / training-37 P1 — route_v2 and route_v1_clean blind to short commands.
8. training-8 / training-15 P1 — adjudicator sees gold; no per-label stop gate.
9. training-24 / 25 / 26 / 28 P1 — ASK undercoverage, weak labels, pronoun ARGS, media_control in Premiere.

## Next moves
1. Read the Tinker console before any more sampling; about $4 left to $148. Unify thresholds.
2. router-it3 is on main: run test_route_parity v3 + router_check val/route_v2 on the Mac (free).
3. CPU near-dup audit of the v3m pool vs route_v2; apply the it3 ship rule on the clean subset.
4. Fix the memory-eval gate tuple shape before any route rebuild.
5. Send planner-lora step 36 and step 72 to the Mac holdout matrix; dev can't pick between them.
