# Handoff: cloud/decisions (generalist System One decisions)

Updated: 2026-10-24 ~21:00 UTC

## State
- Done:
  - research (`docs/decisions_research.md`);
  - Tinker System One backend (`bench/systemone/tinker_backend.py`, `--backend tinker`);
  - generation pipeline (`training/decisions/`);
  - v1 data;
  - multi-task trainer;
  - LR pilot (2 arms);
  - full 1-epoch run `dec-full-lr2e4` (347 steps).
- In flight:
  - calibrated (T_p/T_c fitted on synthetic dev) JevBench + typed-decisions eval of the full run (`runs/decisions/eval_bench/dec-full-lr2e4-cal`);
  - full route val eval of the full run.
- Not started:
  - epoch-2 decision (ask the lead first, with the curve);
  - folding in the data-decisions builder's new code-gold data (only if it helps on dev);
  - final report `training/decisions/reports/results.md` with H1–H6 confirmed/refuted.

## Next steps
1. `uv run --project ml python -m training.decisions.eval_route --tinker-path <full final sampler>`, set `val` and `route_v1` (see `--help`). Compare with the it2-final bar below.
2. Finish the calibrated bench eval: `training/decisions/eval_bench.py --tinker-path <sampler> --temperature-probs Tp --temperature-conf Tc` (T from `training/decisions/calibrate.py`, synthetic dev only).
3. Write `results.md`: base / pilot LR2 / pilot LR4 / full (uncal and cal) / it2-final. Report each of H1–H6 (`docs/decisions_research.md`) as confirmed or refuted.
4. Gate: JevBench, TD and route val must each be ≥ the best single-purpose model. If route val is more than 1 point below it2-final, recommend two adapters (route = it2, System One = ours).

## Artifacts
- Branch `cloud/decisions` on `ardahk/muselet`.
- Data: HF `jonsnov/muselet-decisions-v1` @ `9683da5aff5eea74749c3111186841e6d96d4d79` (3,671 states / 15,167 decisions; 3,487 train / 184 dev states). Pilot: `jonsnov/muselet-decisions-pilot`.
- Route data: `jonsnov/muselet-route-datums-it2b` @ `8df540b`, it2 sampling recipe, seed 0, route 0.6 / ARGS 0.4.
  - NEVER use `muselet-route-datums-it2`: it contains near-duplicates of route_v1.
- Checkpoints: every path is in `training/decisions/reports/checkpoints.jsonl`.
  - Full run: `tinker://80926e89-8087-5481-b535-3bbf70f32c0d:train:0/sampler_weights/dec-full-lr2e4-final` (state: `.../weights/dec-full-lr2e4-final`).
  - LR pilot: sessions `69bac09b-…` (2e-4) and `35f28b5d-…` (4e-4).
  - it2-final bar: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/sampler_weights/it2-final`.
- Run dirs (gitignored, on the original VM only):
  - `runs/decisions/train/<run>/metrics.jsonl`;
  - `runs/decisions/eval_bench/<run>/`;
  - `runs/decisions/eval_route/<run>/`;
  - `runs/bench/{jevbench,typed_decisions}/<ts>/summary.json`.

## Results so far
All on the Tinker backend, uncalibrated.

| model | JevBench easy / original / hard | TD overall | TD choice / noul / score | TD KL | route val top-1 / mF1 | route_v1 top-1 |
|---|---|---|---|---|---|---|
| base Qwen3.5-4B | 1.000 / .847 / .613 (.766) | .581 | .607 / .635 / .520 | .895 | n/a | n/a |
| pilot LR 2e-4 | 1.000 / .931 / .658 (.814) | .638 | .638 / .630 / .644 | .403 | 91.78 / 91.28 | 93.57 |
| pilot LR 4e-4 | 1.000 / .889 / .604 (.775) | .658 | .653 / .670 / .651 | .408 | 89.39 / 88.64 | 92.14 |
| full LR 2e-4 | 1.000 / .944 / .622 | .6645 | .693 / .688 / see summary | .489 | pending | pending |
| it2-final | n/a | n/a | n/a | n/a | 93.67 / 93.04 | 95.00 |

## Spend
- Generation (OpenAI + Anthropic): $52.89 cumulative. The lead allows about $120 if it measurably helps.
- Tinker:
  - base baselines about $0.31;
  - LR pilot about $11.7 (preflight);
  - full run preflight about $22.8 (≤ $24 cap).
  - Aim for ≤ $35 total for this lane. Billing lags: `python3 tools/tinker_spend.py`.

## Open questions for the lead
- Epoch 2? Synthetic dev is near ceiling (choice .964, noul .967, score .938 at step 347). It is probably inflated by template sharing between train and dev, so it is a weak signal.
- Full-run hard tier (.622) is below pilot LR2 (.658), even though the full run has more data. Under investigation; it could be noise (111 items) or over-fitting to the templates.

## Gotchas
- Primary model never trains on typed-decisions or JevBench public data.
- Decontaminate against the five eval sets only (JevBench public, TD test, route_v1, live_t1, external/utterances), not against our own pilot.
- Tinker bf16 numbers are not comparable with the Mac 4-bit numbers; compare on the same backend.
- MLX is imported lazily (Linux test collection).
- Tinker latency is about 6.5 s p50 under bench concurrency; that is not a model-speed measurement.
- ARGS raw exact match collapses when there is little ARGS data; runtime-prefill exact match is the robust number.
