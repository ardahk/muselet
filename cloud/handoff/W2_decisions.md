# W2: General decision model (DeskMind's benchmarks): finish, calibrate, evaluate, export

Repo `ardahk/muselet`. Read `docs/HANDOFF.md` and `AGENTS.md` (Decision API: choice/bool/score, soft labels) first.
You take over the old org's "decisions" builder. Its branch is `cloud/decisions`: trainer
`training/decisions/*`, calibration, and the LR pilot record (commit 694c198).

## Goal
Beat DeskMind brain-4b on **JevBench public** (.831) and **typed-decisions test** (.658), measured on the same Mac
with the same harness (`bench/run_jevbench.sh`, `bench/run_typed_decisions.sh`, System One shim
`bench/systemone`). Today Muselet's base Qwen3.5-4B scores .719 / .569 on the Mac.

## State at handoff
- **Data:** `jonsnov/muselet-decisions-v1` @ `9683da5`: about 14.4k train decisions, about 2,220 code-gold
  states, decontaminated against JevBench, the typed-decisions test, route_v1/v2, live_t1, HobbyLM and DeskMind.
  The data-decisions builder (branch `cloud/data-decisions`) is adding diverse code-gold families (counting,
  multi-hop, long-policy rule engine, dates/business days, thresholds, Bayes, traps) as a new dataset version.
- **LR pilot** (Tinker, bf16, uncalibrated) at 2e-4: JevBench .814 (hard .658), TD .638, route val 91.8.
  4e-4: .775 / .658 / 89.4. Base: .766 / .581.
- **Full run launched** by the old builder: v1 train + 30k it2b route/ARGS, 1 epoch, LR 2e-4, from base, dev and
  route evals every 100 steps, about $23.
- **Hypotheses:**
  - JevBench ≥ .83 (hard ≥ .68);
  - TD ≥ .66 (score ≥ .66);
  - route val ≥ 92.7;
  - after calibrating T_p and T_c on synthetic dev: TD KL ≤ .35, ECE ≤ .06.

## Steps
1. Find the full run's state: Tinker run list, checkpoints and branch commits.
   - **If it finished:** evaluate it.
   - **If it failed or never started:** relaunch with the same config, after a cost check (total Tinker ≤ $140).
2. **Calibrate.** Fit a probability temperature T_p (for KL/Brier) and a confidence temperature T_c (for ECE)
   on the synthetic dev split only.
3. **Evaluate.**
   - JevBench public, broken down easy/original/hard, and typed-decisions test, broken down
     choice/noul/score with KL, Brier and ECE: Tinker sampler first, then the Mac MLX export.
   - Always disclose `normalized_answers` counts for DeskMind (their server returns noul/score without
     probabilities; see `bench/RUNBOOK.md` §Mac results).
   - Don't pick checkpoints on JevBench/TD: use dev.
4. **If route val is more than 1 point under it2**, keep two adapters: it2 (or it3) for routing, the decisions
   LoRA for generic decide(). Otherwise one adapter can serve both. Say which in the PR.
5. **Export:** MLX 4-bit, untied lm_head, a new HF repo or revision (`jonsnov/muselet-decisions-4b-mlx4`). Add a
   `--decide-model` flag in the System One shim (`bench/systemone/cli.py`) and the brain.
6. **Mac run** (Mac agent): `bash bench/run_jevbench.sh --url http://127.0.0.1:8793 --model muselet-dec` and
   `bench/run_typed_decisions.sh`, serving the export through the shim. One model process at a time.

## Acceptance
- A table vs base and DeskMind 4B/0.8B on the same Mac, with every number traceable to a run dir.
- The contamination report (0 overlaps) for the exact train set used.

## Pitfalls
- The first route-only LoRA *hurt* generic decisions (.649 / .473). Keep the multi-task mix.
- ARGS raw exact collapsed in the pilot (46.7%) while runtime-prefill exact stayed at 80%. Report both.
