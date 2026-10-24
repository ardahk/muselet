# training lane digest — pass 23 (main d514300, cloud/data-pipeline f13aa6d, wip/local b63699f, cloud/decisions c08a96d, cloud/brain-5 b752261, cloud/hobby-gaps 929b931)

Open: 1 P0, 12 P1, 12 P2. Pass 23: new training-35 (P1); training-30 P1->P2 (main now serves base ARGS); training-23 re-confirmed (now the serve default).

## Open P0/P1 (ranked)
1. **training-23 (P0, main)** — default router `route-4b-main-mlx4` (serve_brain.sh:12-15) trained on stale pre-fix route data; tau .55 fitted on its stale val rows.
2. **training-35 (P1, main)** — that same mlx4 export folded the head LoRA into tied embeddings (f39efe4), shifting all input embeddings; the served router is not the validated model. Untie fix is branch-only.
3. **training-32 (P1, cloud/decisions)** — spec'd >=30% route replay unimplemented; H6 judged on route_v1; replay must not use stale dedup data.
4. **training-31 (P1, cloud/hobby-gaps)** — set_brightness catalog change breaks route render parity 50/50 without a version bump.
5. **training-29 (P1, data-pipeline)** — short_edit1 decontam drops 62/423 short items, mostly spurious.
6. **training-5 (P1)** — two Tinker spenders, per-run guards only, billing lags.
7. **training-14 (P1, main)** — 36-option parity reference vs 41-option catalog; pitch claims byte-identical.
8. **training-26 / training-28 (P1, data-pipeline)** — pronoun ASK relabeled concrete; media_control in Premiere 7.9%.
9. **training-24 / training-25 (P1)** — ASK undercoverage; weak labels media_control/dark_mode/find_file.
10. **training-8 / training-15 (P1, data-pipeline)** — no 15% adjudication STOP; teacher subset skew.

## Next moves (max 5)
1. Re-export main-final with `export untie` (free), re-run router_check + mlx_parity, refit tau; switch serve default only if it wins.
2. Fix short_edit1, pronoun ASK and media_control contexts, then launch it2 from route_train with the pinned split (~$29), answer-only ARGS, untied export.
3. Decisions joint run: replay from post-fix route_train only, judge H6 on route_val.
4. Hold hobby-gaps until the catalog version bump + regenerated render samples/parity_300; merge the 41-option parity file before the byte-identical claim ships.
5. One shared Tinker ledger for all workers; cap each run at 150 - billed - unbilled estimates.
