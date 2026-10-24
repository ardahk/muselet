> **2026-10-24 23:15 UTC (decisions-2):** calibrated cross-check done and Mac export uploaded — see `results.md` and the PR #39 `## Handoff` (current source of truth).

# Handoff: cloud/decisions (generalist System One decisions), PR #39

Updated: 2026-10-24 21:25 UTC (org cut-over). Branch `cloud/decisions`, PR https://github.com/ardahk/muselet/pull/39 (not merged).

## Goal
Make one Qwen3.5-4B LoRA (Tinker) that serves both System One typed decisions (`choice`/`noul`/`score`, answer-token logits after a prefilled `choice#`) and route/ARGS. It must beat DeskMind G18b on JevBench (.831) and typed-decisions zero-shot (.658), with route val within 1 pt of it2-final. If route can't hold, ship two adapters: route = it2, System One = ours.

Gate: JevBench, TD and route val must each be ≥ the best single-purpose model.

## State
- **Done:**
  - research (`docs/decisions_research.md`, hypotheses H1–H6);
  - Tinker System One backend (`bench/systemone/tinker_backend.py`);
  - data pipeline (`training/decisions/`, `SPEC.md` plus amendments);
  - v1 data on HF;
  - trainer, calibration and evals;
  - 2-arm LR pilot;
  - full 1-epoch run `dec-full-lr2e4` (347 steps, finished);
  - calibration fit;
  - uncalibrated JevBench + TD of the full run.
- **In flight at cut-over:** calibrated JevBench + TD eval of the full run. It is a local process on the old VM, so it dies with it; re-run it (step 1). No Tinker training job is running.
- **Not started:**
  - full route val + route_v1 eval of the full run (step 2);
  - `results.md`;
  - epoch-2 decision (the lead must approve; send the curve);
  - folding in the data-decisions builder's (session 7812ccea) new code-gold data, only if it helps on dev.

## Resume (commands from repo root; need TINKER_API_KEY and HF_TOKEN)
```
uv sync --project ml
S=tinker://80926e89-8087-5481-b535-3bbf70f32c0d:train:0/sampler_weights/dec-full-lr2e4-final
mkdir -p runs/decisions/train/dec-full-lr2e4 && cp training/decisions/reports/snapshots/dec-full-lr2e4.calibration.json runs/decisions/train/dec-full-lr2e4/calibration.json
# 1. calibrated bench (JevBench via bench/run_jevbench.sh + TD via bench/typed_decisions.py), ~1 h, ~$0.3
uv run --project ml python -m training.decisions.eval_bench --sampler $S --name dec-full-lr2e4-cal \
  --output runs/decisions/eval_bench/dec-full-lr2e4-cal/metrics.json --calibration runs/decisions/train/dec-full-lr2e4/calibration.json
# 2. route val (1216) + ARGS val (878) + route_v1 (140); default --datums = it2b@8df540b
uv run --project ml python -m training.decisions.eval_route --sampler $S --name dec-full-lr2e4 \
  --output runs/decisions/eval_route/dec-full-lr2e4/metrics.json
# (re-fit calibration if needed; synthetic dev ONLY)
uv run --project ml python -m training.decisions.calibrate --help
# training CLI (dry-run first; aborts >$25 without --approved-over-25)
uv run --project ml python -m training.decisions.train --help
```
The full run was launched with:
- `--name dec-full-lr2e4`, `--init-from Qwen/Qwen3.5-4B` (base, NOT main-final);
- all v1 train, no `--subset`;
- `--route-datums jonsnov/muselet-route-datums-it2b@8df540b --route-size 30000`;
- `--learning-rate 2e-4 --rank 32 --batch-size 128 --epochs 1 --eval-every 100 --seed 0 --max-usd 24`.

An epoch 2 would continue from state `tinker://80926e89-8087-5481-b535-3bbf70f32c0d:train:0/weights/dec-full-lr2e4-final`. Check `train.py --help` for the resume flag; ask the lead first.

## Artifacts
- Commits:
  - `3a865a0` Tinker backend;
  - `c6f8491` pipeline;
  - `d8a1f51` mini-check;
  - `e125c13` full generation;
  - `184c80f` trainer;
  - `43abfa3` lazy MLX;
  - `694c198` pilot checkpoints;
  - `b78d778` full checkpoints;
  - this commit: handoff plus copied metrics.
- Data:
  - generic: `jonsnov/muselet-decisions-v1` @ `9683da5aff5eea74749c3111186841e6d96d4d79` (3,671 states / 15,167 decisions; 3,487 train / 184 dev states; 0 overlaps after decontamination);
  - pilot: `jonsnov/muselet-decisions-pilot`;
  - route/ARGS: `jonsnov/muselet-route-datums-it2b` @ `8df540b`, it2 recipe `random.Random(0)`, route 0.6 / ARGS 0.4.
- Tinker checkpoints: all in `training/decisions/reports/checkpoints.jsonl`.
  - **Full run** (session 80926e89-8087-5481-b535-3bbf70f32c0d):
    - sampler `.../sampler_weights/dec-full-lr2e4-final`, state `.../weights/dec-full-lr2e4-final`;
    - also step-100, step-200, step-300 and step-347.
  - Pilot 2e-4: `tinker://69bac09b-ecd4-5b8b-b867-c92075b511c5:train:0/sampler_weights/dec-pilot-lr2e4-final`.
  - Pilot 4e-4: `tinker://35f28b5d-15fc-5eb5-ade8-86264f1d4c5f:train:0/sampler_weights/dec-pilot-lr4e4-final`.
  - Route bar it2-final: `tinker://73495408-9d6d-56b5-9e1a-894744c13add:train:0/sampler_weights/it2-final`.
- Calibration (full run, fitted on synthetic dev only): T_p = 0.9048, T_c = 0.7408. Copy: `training/decisions/reports/snapshots/dec-full-lr2e4.calibration.json`.
- Metrics copies (because `runs/` is gitignored): `training/decisions/reports/snapshots/`.
  - Train curves: `*.metrics.jsonl`.
  - Route evals: `route-*.json`.
  - Bench evals: `bench-*.json`.
  - Raw run dirs were on the old VM only.

## Results (Tinker bf16, uncalibrated unless noted)
| model | JevBench easy / orig / hard (total) | TD overall | TD choice / noul / score | TD KL | route val top-1 / mF1 | ARGS raw / runtime EM | route_v1 top-1 / mF1 |
|---|---|---|---|---|---|---|---|
| base Qwen3.5-4B | 1.000 / .847 / .613 (.766) | .581 | .607 / .635 / .520 | .895 | n/a | n/a | n/a |
| pilot 2e-4 (4k generic + 6k route/ARGS) | 1.000 / .931 / .658 (.814) | .638 | .638 / .630 / .644 | .403 | 91.78 / 91.28 | 46.7 / 80.75 | 93.57 / 95.26 |
| pilot 4e-4 | 1.000 / .889 / .604 (.775) | .658 | .653 / .670 / .651 | .408 | 89.39 / 88.64 | 0.0 / 80.18 | 92.14 / 92.00 |
| full 2e-4 (all v1 + 30k route/ARGS) | 1.000 / .944 / .622 (~.801) | .6645 | .693 / .688 / see bench json | .489 | TODO (subset of 300: .920) | TODO | TODO |
| it2-final (route-only) | n/a | n/a | n/a | n/a | 93.67 / 93.04 | 86.33 / 86.90 | 95.00 / 94.82 |
| Mac reference: DeskMind G18b 8-bit | 1.000 / .958 / .676 (.831) | .658 | .657 / .702 / .626 | n/a | n/a | n/a | n/a |

Full-run synthetic dev, accuracy (KL):

| step | choice | noul | score |
|---|---|---|---|
| 100 | .822 (.496) | .935 (.169) | .837 (.349) |
| 200 | .935 (.175) | .931 (.178) | .918 (.188) |
| 300 | .968 (.145) | .975 (.083) | .923 (.170) |
| 347 | .964 (.149) | .967 (.106) | .938 (.151) |

Route subset top-1: .913 / .923 / .923 / .920.

Interpretation:
- Synthetic dev has plateaued and is near ceiling; it is likely inflated by templates shared between train and dev. So there is no clear case for epoch 2 from dev.
- The full run's JevBench hard tier (.622) is below pilot 2e-4 (.658). Possibly noise (111 items) or template over-fitting; not yet investigated. Look at per-family hard results in `runs/bench/jevbench/<ts>/hard/`.
- Route at a 30k mix looks about 1.5–2 pt below it2. If confirmed by step 2, report it to the lead and recommend two adapters.

## Spend
- Generation (OpenAI + Anthropic): $52.89 cumulative. The lead allows up to about $120 if it measurably helps.
- Tinker (preflight estimates):
  - baselines $0.31;
  - pilot 2 × $5.86;
  - full run about $22.8 (cap $24).
  - Lane total about $35. Billing lags: `python3 tools/tinker_spend.py` (it read $64.89 month-to-date at 18:29 UTC, before the full run billed). Shared hard cap $150; aim for this lane ≤ $35, so no more training without asking the lead.

## Open questions for the lead
1. Two adapters vs multi-task, once full route val is measured.
2. Epoch 2: not recommended on the current evidence (dev plateaued).
3. Whether to spend more generation money on less templated code-gold data, which might fix the hard tier. The data-decisions builder is already producing new generators.

## Gotchas
- Never train on typed-decisions (train or test) or JevBench public data. Decontaminate new data against the five eval sets only (JevBench public, TD test, `evals/route_v1.jsonl`, `evals/live_t1.jsonl`, `evals/external/utterances.jsonl`), not against our own pilot data.
- Never use `jonsnov/muselet-route-datums-it2`: it has near-duplicates of route_v1. Use it2b@8df540b.
- Do not init from main-final: route-only training damaged generic skills (lead's Mac measurement).
- Tinker bf16 is not comparable with the Mac 4-bit numbers; compare on the same backend.
- Tinker latency is about 6.5 s p50 under bench concurrency; it is not a speed measure.
- MLX imports are lazy, so Linux pytest works: `uv run --project ml python -m pytest bench/tests -q` gave 207 passed, 2 skipped.
- ARGS raw EM collapses with little ARGS data; runtime-prefill EM is the robust metric.
- Calibration: T_p scales probabilities; T_c is a separate distribution for choice/score confidence; noul has no confidence field.
- CI on PR #39 has not been checked yet.
