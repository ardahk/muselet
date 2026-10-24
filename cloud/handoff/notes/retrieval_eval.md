| k | set | pass rate | n_pass/n | prompt tokens mean | dynamic tokens mean | TTFT p50 ms |
|---:|---|---:|---:|---:|---:|---:|
| 0 | v1-tune | 0.840 | 21/25 | 3149.0 | 116.0 | 74.4 |
| 0 | v1-holdout | 0.643 | 9/14 | 3126.2 | 93.2 | 74.7 |
| 0 | v1-holdout2 | 0.667 | 8/12 | 3102.8 | 69.8 | 64.7 |
| 0 | v2-holdout | 0.400 | 52/130 | 3284.0 | 251.0 | 113.4 |
| 1 | v1-tune | 0.880 | 22/25 | 3336.5 | 303.5 | 121.6 |
| 1 | v1-holdout | 0.714 | 10/14 | 3316.9 | 283.9 | 119.3 |
| 1 | v1-holdout2 | 0.750 | 9/12 | 3298.4 | 265.4 | 117.5 |
| 1 | v2-holdout | 0.462 | 60/130 | 3477.2 | 444.2 | 184.6 |
| 2 | v1-tune | 1.000 | 25/25 | 3507.1 | 474.1 | 179.2 |
| 2 | v1-holdout | 0.714 | 10/14 | 3476.1 | 443.1 | 168.8 |
| 2 | v1-holdout2 | 0.750 | 9/12 | 3474.1 | 441.1 | 175.0 |
| 2 | v2-holdout | 0.462 | 60/130 | 3650.4 | 617.4 | 269.4 |
DECISION: ship retrieval_k=1
k=1: gain +0.072 -> PASS
k=2: gain +0.072 -> FAIL (TTFT p50 > +150 ms: v2-holdout +156)

## Run details (sidekick, 2026-10-24)
- Config (verified shipped, k=0 reproduces): `--model mlx-community/Qwen3.5-4B-4bit --history dsl --constrain --done-alone --system-extra prompts/planner_fewshot.md`, bank `v2-tune` default, greedy. k=0: holdout .643 (ship .643), holdout2 .667 (ship .667) — exact reproduction.
- Commands: `evals/planner_offline.py --set <tune|holdout|holdout2> --retrieval-k <k> --tag ret_k<k>_<set>` (v1); `evals/planner_v2_run.py --v2-set v2-holdout --retrieval-k <k> --tag ret_k<k>_v2ho` (v2).
- Result files: runs/planner_offline/ret_k{0,1,2}_{tune,ho,ho2,v2ho}.json (symlinked to ret-k{K}-{v1tune,v1holdout,v1holdout2,v2holdout}.json for the reporter).
- plan_ms p50 (per-turn): tune 145/226/289, ho 144/257/268, ho2 120/189/234, v2ho 246/343/460 ms for k=0/1/2.
- strict_pass == pass in every cell. One model process at a time; all exited.
