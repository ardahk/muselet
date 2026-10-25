# System One decisions LoRA — results

Model: Qwen3.5-4B + LoRA (rank 32), `dec-full-lr2e4`: 347 steps, 1 epoch, LR 2e-4, batch 128, seed 0, all v1 generic
decisions plus 30k it2b route/ARGS datums. Tinker sampler
`tinker://80926e89-8087-5481-b535-3bbf70f32c0d:train:0/sampler_weights/dec-full-lr2e4-final`.
Mac export: HF `jonsnov/muselet-decisions-4b-mlx4` @ `8a8807db0d78efe10784781140d6496f5b144616` (MLX 4-bit, untied `lm_head`,
`calibration.json` included). Raw metrics: `reports/snapshots/bench-*.json`.

All numbers below are **Tinker bf16** (cloud). They are not comparable with Mac MLX 4-bit numbers; the Mac run is the
PR #39 "Mac requests" item.

## 1. Development metrics (synthetic dev split, not a benchmark)

The dev split (184 states, `jonsnov/muselet-decisions-v1` @ `9683da5`) comes from the same generators as train, so it is
optimistic. It was used only for checkpoint monitoring and for fitting calibration.

Accuracy (KL from soft gold), full run:

| step | choice | noul | score |
|---|---|---|---|
| 100 | .822 (.496) | .935 (.169) | .837 (.349) |
| 200 | .935 (.175) | .931 (.178) | .918 (.188) |
| 300 | .968 (.145) | .975 (.083) | .923 (.170) |
| 347 | .964 (.149) | .967 (.106) | .938 (.151) |

Calibration fit on dev (`reports/snapshots/dec-full-lr2e4.calibration.json`):

| temperature | value | used for |
|---|---|---|
| T_p | 0.9048 | answer probabilities |
| T_c | 0.7408 | choice/score confidence |

## 2. Benchmark metrics (public evals; never trained or tuned on)

### JevBench (accuracy; Brier / ECE)

| model | easy (48) | original (72) | hard (111) | total (231) |
|---|---|---|---|---|
| base Qwen3.5-4B | 1.000 | .847 | .613 | ~.766 |
| pilot 2e-4 (4k generic + 6k route/ARGS) | 1.000 | .931 | .658 | .814 (.260 / .050) |
| pilot 4e-4 | 1.000 | .889 | .604 | .775 (.265 / .064) |
| full 2e-4, uncalibrated | 1.000 | .944 | .622 | .801 (.297 / .080) |
| full 2e-4, calibrated (T_p, T_c) | 1.000 | .944 | .622 | .801 (.302 / .095) |
| *Mac ref: DeskMind brain-4b (G18b 8-bit)* | 1.000 | .958 | .676 | .831 |

### typed-decisions (`LocalLLaMA/typed-decisions` @ `80cb93a`; 400 cases / 2000 decisions; accuracy, KL in parentheses)

| model | overall | choice (600) | noul (600) | score (800) | overall Brier / ECE |
|---|---|---|---|---|---|
| base Qwen3.5-4B | .581 (.895) | .607 | .635 | .520 | — |
| pilot 2e-4 | .638 (.403) | .638 (.410) | .630 (.417) | .644 (.388) | .200 / .085 |
| pilot 4e-4 | .658 (.408) | .653 (.465) | .670 (.397) | .651 (.374) | .202 / .074 |
| full 2e-4, uncalibrated | .6645 (.489) | .693 (.394) | .688 (.616) | .625 (.464) | .219 / .104 |
| full 2e-4, calibrated | .6625 (.562) | .690 (.452) | .687 (.696) | .624 (.542) | .234 / .123 |
| *Mac ref: DeskMind brain-4b* | .658 | .657 | .702 | .626 | — |

Normalized answers (`noul_from_value`, `score_onehot_from_value`) were 0 / 0 in every run above. The TD request latency
p50 was ≈6.6 s in every run; that is Tinker round-trip time, not a speed measurement.

## 3. Reading

- **Accuracy.** The full run beats base on TD (+8.4 pts) and is at the brain-4b reference on Tinker (.6645 vs .658).
  On JevBench it is 3 pts below brain-4b (.801 vs .831). The gap is entirely in the hard tier (.622 vs .676), and the
  pilot 2e-4 hard tier (.658) was better. This looks like over-fitting to templated data; it was not fixed because no
  more training is allowed.
- **Calibration hurts on the benchmarks.** The dev-fitted temperatures are both below 1, so they sharpen the
  distributions. That worsens KL, Brier and ECE on both benchmarks (TD KL .489 → .562; JevBench total ECE .080 → .095).
  Accuracy is unchanged up to ±0.2 pt: the score accuracy depends on the tempered distribution, and Tinker
  logprobs have run-to-run noise.
  - Synthetic dev is over-confident-friendly; the benchmarks are not.
  - **Recommendation:** on the Mac, serve uncalibrated (T = 1) unless the Mac calibrated run says otherwise.
    `calibration.json` ships so either choice is one flag.
- **Gate status.** Not yet met: JevBench must reach ≥ .831 and TD ≥ .658 on the same Mac harness. The final call needs
  the Mac MLX 4-bit run.
