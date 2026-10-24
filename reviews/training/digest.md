# training lane digest — pass 29 (main d7c192f, cloud/data-pipeline 0ce9ea6, wip/local 367d450, cloud/decisions 6d395df)

Open: 0 P0, 11 P1, 14 P2. Resolved training-23 (main serves it2, trained on fixed data). New: training-38 (P1), -39, -40 (P2).

## Ranked open P0/P1
1. training-38 P1 — decontam norm() deletes CJK; DeskMind zh items are unchecked and produce false gate hits.
2. training-29 P1 — short_edit1 rule mostly false positives; hard gate in train.py; blocks it2b decisions.
3. training-37 P1 — route_v1_clean is length-skewed; AGENTS.md now mandates quoting only it.
4. training-32 P1 — decisions route replay >=30% unimplemented.
5. training-5 P1 — shared Tinker cap, per-run guards, lagging billing.
6. training-26 P1 — pronoun ARGS treated as concrete (no ASK).
7. training-28 P1 — media_control contexts inside Premiere Pro.
8. training-24 P1 — ASK undercoverage.
9. training-25 P1 — weak labels media_control/dark_mode/find_file.
10. training-8 / training-15 P1 — no per-label adjudication STOP gate; teacher subset skew.

## Next moves
1. Make norm() Unicode-aware and narrow short_edit1; re-run evalcheck on main/it2/it2b.
2. Quote it2 on full route_v1 + clean, split by length; add clean-subset notes for HobbyLM/DeskMind scores.
3. Explain MLX .913 vs Tinker .961 on clean route_v1 (tau vs quant).
4. Implement decisions route replay from fixed route_train before any joint run.
5. One shared Tinker spend ledger.
