# training lane digest — pass 30 (main fbd5aa0, cloud/data-pipeline 735686f, wip/local 2f26223, cloud/pitch-4 6393857, cloud/decisions 6d395df)

Open: 0 P0, 10 P1, 15 P2. Pass 30: training-38 P1->P2 (it2 rows have 0 CJK; normalizer unchanged). training-40 policy on main, disclosures on pitch-4. No new findings.

## Ranked open P0/P1
1. training-29 P1 — short_edit1 rule mostly false positives; hard gate in train.py; blocks it2b decisions.
2. training-37 P1 — route_v1_clean is length-skewed; AGENTS.md now mandates quoting only it.
3. training-32 P1 — decisions route replay >=30% unimplemented.
4. training-5 P1 — shared Tinker cap, per-run guards, lagging billing.
5. training-26 P1 — pronoun ARGS treated as concrete (no ASK).
6. training-28 P1 — media_control contexts inside Premiere Pro.
7. training-24 P1 — ASK undercoverage.
8. training-25 P1 — weak labels media_control/dark_mode/find_file.
9. training-8 / training-15 P1 — no per-label adjudication STOP gate; teacher subset skew.

## Next moves
1. Make norm() Unicode-aware and narrow short_edit1; re-run evalcheck on main/it2/it2b.
2. Quote it2 on full route_v1 + clean, split by length; add clean-subset notes for HobbyLM/DeskMind scores.
3. Explain MLX .913 vs Tinker .961 on clean route_v1 (tau vs quant).
4. Implement decisions route replay from fixed route_train before any joint run.
5. One shared Tinker spend ledger.
