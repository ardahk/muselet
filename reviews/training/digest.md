# training lane digest — pass 46 (main 2a2c2a9, wip/local 4f963a7, memory-eval c05944e)

Open: 1 P0, 14 P1, 15 P2. New: training-49 (memory-eval gate crash) and training-50 (spend threshold conflict).

## Ranked open P0/P1
1. training-44 P0 — it3 needs catalog v3. Runtime env var differs, and main's draft_email index is 29 vs 37 in v3, so special-option ids would shift (after_it3.sh, ml/src/brain/catalog.py).
2. training-50 P1 — spend thresholds conflict ($140 guard/common, $142/$146 planner-lora, $148 user); the stop message goes to one session (tools/tinker_spend.py).
3. training-49 P1 — memory-eval gate appends 2-tuples; overlaps() raises ValueError, so route rebuild is broken (training/data_route/build.py).
4. training-47 P1 — route_v2 gate misses mid-length paraphrases; 13-gram rule can't fire on 640/955 items (evalcheck.py).
3. training-48 P1 — merge_it3cand keeps source splits; val3/tau may be inflated (it3gen.py).
4. training-45 P1 — it3 ARGS audit noise fixed only on the 1,061 sampled rows.
5. training-29 P1 — short_edit1 over-drops short commands.
6. training-43 / training-37 P1 — route_v2 and route_v1_clean blind to short commands.
7. training-8 / training-15 P1 — adjudicator sees gold; no per-label stop gate.
8. training-24 / 25 / 26 / 28 P1 — ASK undercoverage, weak labels, pronoun ARGS, media_control in Premiere.

## Next moves
1. Serve it3 only with MUSELET_SKILLS=training/artifacts/catalog_v3.json (or byte-match main's catalog to v3), parity test on v3 samples, mismatch = fail.
2. CPU near-dup audit of the v3m pool vs route_v2 (char5/bigram); apply the ship rule on the clean subset.
3. Regroup v3m by MinHash family before fitting tau on val3.
4. Spend: unify thresholds to the $148 stop (training-50); ~$10 headroom, ~$10 headroom vs the ~$138 estimate. Enough for evals and parity, not for another training run. Read the console before each sampler call.
5. Re-audit 500 it3 ARGS rows.
