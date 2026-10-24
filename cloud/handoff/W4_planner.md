# W4: Planner (System 2): measure on v2, retrieval examples, optional LoRA

Repo `ardahk/muselet`. Read `docs/HANDOFF.md`, and `AGENTS.md` (planner config, DSL, "never tune on holdouts").

## State
- **Default:** base Qwen3.5-4B-4bit, greedy, `prompts/planner_fewshot.md` (rules 16–18 + examples), DSL history,
  line-start op constraint, done-alone. About 139 ms per turn p50, TTFT 72 ms, 83 tok/s.
- **v1 offline bench** (`evals/planner_offline.py`, 25 tune / 14 holdout / 12 holdout2): .88 / .643 / .667.
  35B-A3B: .84 / .71 / –. 9B is worse.
- **v2 bench** (merged): `evals/planner_scenarios_v2.jsonl`, 260 scenarios; run it with `evals/planner_v2_run.py
  --v2-set v2-tune|v2-holdout`. No model has been measured on v2 yet.
- **planner-retrieval** builder (`cloud/planner-retrieval`): BM25 1–2 shot examples from v2-tune gold replies,
  `--planner-retrieval-k`. Pre-registered rule: ship k > 0 only if the mean holdout pass (v1-holdout,
  v1-holdout2, v2-holdout) improves by ≥ 3 points, with no set dropping by more than 1 scenario, and TTFT
  +≤ 150 ms.
- Teacher demos (W3 lane 3) will give a larger bank and SFT data.

## Steps (a Mac agent runs the model evals; one model process at a time; memory ≥ 40)
1. Baseline on v2: the default 4B config on v2-tune and v2-holdout, and the 35B on v2-holdout. Record pass,
   strict, per category, and TTFT/turn latency.
2. Retrieval eval per the pre-registered rule (k = 0/1/2, across all holdouts). If it ships, set the flag in
   `tools/serve_brain.sh` and keep k = 0 selectable.
3. **Optional planner LoRA**, only if the Tinker budget allows after W1/W2 (total ≤ $140):
   - SFT on the demos, rendered without few-shot. Roughly 3–6M tokens at about $0.78/M, so $5–10 per epoch.
   - Hypothesis: + holdout pass with a shorter prompt (faster TTFT).
   - Evaluate tuned vs tuned: the LoRA without few-shot vs the base with few-shot (+ retrieval if it shipped).
4. Turn every live planner failure from `runs/bench/live/*/results.jsonl` into a v1-style regression scenario in
   `evals/` (lead approval needed for `evals/` edits).

## Acceptance
Numbers tables with config + run dirs. Defaults change only per a pre-registered rule.
