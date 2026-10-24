# training lane digest — pass 19 (main 28dc259, cloud/data-pipeline 80cb13f, wip/local e1701a3, cloud/brain-4 3aca368, cloud/hobby-gaps 14ff59b)

Open: 1 P0, 11 P1, 9 P2. New this pass: training-29, -30, -31. training-27 downgraded P1->P2 (it2 plan now selects on route_val only).

## Open P0/P1 (ranked)
1. **training-23 (P0, main)** — shipped router `route-4b-main` trained on stale pre-fix route data; `evals/router_check.py` still runs it. it2 plan pins main's split, but no retrain yet.
2. **training-30 (P1, main)** — main's ARGS datums weighted the runtime-prefilled empty think block; per 80cb13f this makes the runtime ARGS line empty. Reported ARGS EM 0.869 is not runtime-equivalent; `router_check.py --args-model` can now measure it.
3. **training-31 (P1, cloud/hobby-gaps)** — set_brightness description/args change (level|delta, require_one_of) without a version bump: 50/50 route render samples mismatch, `test_samples_reproduce` fails; no ARGS data has `delta`.
4. **training-29 (P1, data-pipeline)** — short_edit1 decontam drops 62/423 short committed items, mostly spurious (`play`~`archive`, `open chrome`~`open finder`); open_app loses 17/34 short items, open_folder 13/32.
5. **training-5 (P1)** — two Tinker spenders, per-run guards only, billing lags hours; ~$81 left.
6. **training-14 (P1, main)** — parity reference is 36-option vs 41-option catalog; parity test xfails while pitch claims byte-identical rendering.
7. **training-26 (P1, data-pipeline)** — it2 ASK generator now explicitly asks for pronoun args, but ask_rule still calls `to="him"` concrete -> relabeled to the skill.
8. **training-28 (P1, data-pipeline)** — gen note excludes Premiere, but contexts.py still puts 7.9% of media_control in Premiere Pro.
9. **training-24 (P1)** — ASK undercoverage (val 0/3).
10. **training-25 (P1)** — weak labels media_control 0.32, dark_mode 0.68, find_file 0.71.
11. **training-8 / training-15 (P1, data-pipeline)** — no per-label 15% adjudication STOP; teacher subset skew / hard-soft mixing.

## Next moves (max 5)
1. Before the it2 launch: fix short_edit1 (skip 1-token items, only allow near-variant/stopword substitutions, per-label drop report), the pronoun ASK rule and media_control context sampling.
2. Run `evals/router_check.py --args-model` on route-4b-main to get real runtime ARGS/e2e numbers; don't quote 0.869 until then.
3. Hold cloud/hobby-gaps until the catalog version is bumped and render samples + parity_300 + delta ARGS data are regenerated in the same retrain.
4. Merge the 41-option parity reference before the byte-identical claim ships.
5. One shared spend ledger for both Tinker workers; cap each run at 150 - billed - unbilled estimates.
