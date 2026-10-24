# training lane digest — pass 35 (main c949565, cloud/decisions e125c13, cloud/data-pipeline 512cce0, wip/local 4ec066f)

Open: 0 P0, 11 P1, 14 P2. New: training-41 (P1), training-42 (P2). main/wip: briefs only, nothing in lane.

## Ranked open P0/P1
1. training-41 P1 — decisions full data: pilot 13-gram decontam deleted the templated code-gold families (counting/multi-hop/long-policy 0, numeric 1; 301/2,224 code states kept).
2. training-32 P1 — decisions data uploaded without the required >=30% route replay.
3. training-29 P1 — short_edit1 rule mostly false positives; hard gate in train.py; blocks it2b.
4. training-37 P1 — route_v1_clean length-skewed; no full/short-command number for it2.
5. training-5 P1 — shared Tinker cap; decisions Tinker run (~$12) has no shared-cap guard.
6. training-26 P1 — pronoun ARGS treated as concrete (no ASK).
7. training-28 P1 — media_control contexts inside Premiere Pro.
8. training-24 P1 — ASK undercoverage.
9. training-25 P1 — weak labels media_control/dark_mode/find_file.
10. training-8 / training-15 P1 — no per-label adjudication STOP gate; teacher subset skew.

## Next moves
1. Re-run decisions decontam on the labeled records without pilot template 13-grams (no API spend), re-upload.
2. Add route replay from fixed route_train (pinned split) before any decisions Tinker run; judge H6 on route_val.
3. Narrow short_edit1; re-run evalcheck on it2b.
4. Quote it2 on full route_v1 + clean, split by length; explain MLX .913 vs Tinker .961.
5. One shared Tinker spend ledger before the decisions run.
