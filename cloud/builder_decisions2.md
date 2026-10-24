# Lane: decisions-2 — finish the System One decisions LoRA: export for the Mac, results, mergeable PR

Brief of record: `cloud/handoff/W2_decisions.md`. Continue from branch `cloud/decisions` @ `f6fb133` (PR #39);
read `training/decisions/HANDOFF.md` and the PR's `## Handoff` first.

## State
- Full run `dec-full-lr2e4` (347 steps) finished. Sampler:
  `tinker://80926e89-8087-5481-b535-3bbf70f32c0d:train:0/sampler_weights/dec-full-lr2e4-final`.
  Calibration fit: `training/decisions/reports/snapshots/dec-full-lr2e4.calibration.json`.
  Uncalibrated JevBench/TD snapshot: `training/decisions/reports/snapshots/bench-dec-full-lr2e4-uncal.json`.
- **No more training** (Tinker is at ~$136 of $150): no epoch 2, no code-gold v2 retrain. The route/ARGS role stays
  with the router lane (it2/it3); this adapter is System One only, so skip the route evals.

## Tinker cap for this lane: $0.50 (sampling only)
Allowed: the calibrated JevBench + typed-decisions cross-check on the Tinker sampler (~$0.3, step 1 of the old
handoff). Nothing else.

## Do
1. Run the calibrated cross-check (old handoff step 1) and record it in `training/decisions/results.md` together
   with the pilot, uncalibrated and calibrated numbers (dev numbers clearly separated from benchmark numbers).
2. **Export** the final weights to MLX 4-bit with the **untied lm_head** → new HF repo
   `jonsnov/muselet-decisions-4b-mlx4`, plus the calibration JSON.
3. Make the Mac System One path load it: the shim/server used by `bench/run_jevbench.sh` and
   `bench/run_typed_decisions.sh` (see `bench/systemone/`) must accept the MLX model path and the calibration file,
   so the lead runs JevBench and typed-decisions on the Mac exactly like DeskMind's brain-4b was run (same harness,
   same Mac). Write the exact commands in the PR body.
4. Make PR #39 mergeable: rebase on `main`, all `ml/tests` and `bench/tests` green, `ml/pyproject.toml` /
   `uv.lock` changes minimal and pinned. Keep `## Handoff` current.

API cap for this lane: $5 per provider.
