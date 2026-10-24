# Lane: router-it3 — export, Mac-eval prep and serving integration for router iteration 3

Brief of record: `cloud/handoff/W1_router_it3.md`. Continue from branch `cloud/data-pipeline` @ `830ba35` (PR #2);
read its `## Handoff` section and `training/scripts/it3/` first.

## Verified state (lead, Sat 21:30Z)
- Tinker run `aa6fe792-c23d-5da7-ac51-c3647ae35f5c:train:0` **finished**. Checkpoints that exist:
  `weights/it3-200`, `weights/it3-400`, `weights/it3-final`, `sampler_weights/it3-final`
  (prefix `tinker://aa6fe792-c23d-5da7-ac51-c3647ae35f5c:train:0/`).
- The old VM (`/data`, trainer logs, `final_eval.json`, the `after_it3.sh` evals and the export) is gone unless the
  old agent pushed more commits to `cloud/data-pipeline` after `830ba35`. Check the branch first and reuse anything
  that landed. No it3 model is on HF yet (only `jonsnov/muselet-route-4b-main-mlx4` @ `54b2181` = it2).
- it3 data: `jonsnov/muselet-route-datums-it3` @ `4ded9ab`. Catalog v3: `training/artifacts/catalog_v3.json`.

## Tinker cap for this lane: $1.50 (sampling only, no training)
The heavy evals run on the Mac with the MLX exports (free, and it is the serving path). Use Tinker only for the
parity reference (sampler top-1/probabilities on 300 rendered prompts) and at most one val pass if the export check
needs it.

## Do, in order
1. **Export** `weights/it3-final` (or the sampler weights if that is the downloadable artifact): download → merge
   LoRA with the **untied lm_head** → MLX 4-bit → render check. Push to a **new** HF repo
   `jonsnov/muselet-route-4b-it3-mlx4` (never touch it2's repo/revision). Upload `parity_300.jsonl`
   (300 rendered val prompts + Tinker sampler top-1 and option probabilities) next to the weights.
2. **Contamination gate** on the it3 training pool: `muselet_train.evalcheck.overlaps` against route_v1/v2, live_t1,
   HobbyLM sealed r1–r4, DeskMind diag/dyn/proposals. Must be 0; put the table in the PR.
3. **Serving PR** — new branch `cloud/router-it3-serve` from `main` (leave PR #2 open as the training record; don't
   merge it):
   - bring over only what serving and the Mac evals need: `training/artifacts/catalog_v3.json`,
     `evals/route_v2.jsonl` (sha256 `20cd542b…dd51`), the it3 render samples;
   - `ROUTER=it3` in `tools/serve_brain.sh` with its own tau (placeholder 0.65 until the Mac fit), loading catalog v3
     only when it3 is selected; it2 stays the default and must keep working unchanged;
   - regenerate `training/artifacts/route_render_samples*.jsonl` so the route-parity tests pass for **both** it2
     and it3;
   - make `evals/router_check.py` able to run on the Mac: `--router it2|it3|base`, `--set route_v1_clean|route_v2|val`,
     a tau grid (fit on val only), per-label accuracy, the v2-catalog subset of route_v2, ARGS exact on val, ECE,
     and a parity mode against `parity_300.jsonl` (top-1 agreement, target ≥ 0.99);
   - write the exact Mac commands for the lead in the PR body.
4. Pre-registered ship rule (the lead applies it from the Mac numbers): it3 ships if route_v2 ≥ it2 + 2 pts AND
   route_v1_clean ≥ it2 − 1 pt AND ARGS exact ≥ it2, tuned vs tuned (tau fit on val for each).

## Pitfalls
- Option ids shift in v3 (specials move to `f h i j`); route_v2 is labelled under v3.
- Never select checkpoints or tau on route_v2 / route_v1 / JevBench.
- API cap for this lane: $10 per provider (you should need none).
