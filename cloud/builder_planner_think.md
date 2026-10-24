# Lane: planner-think — let the planner reason before it acts (thinking mode with a token budget)

User decision (Sat evening): "It is okay to lose more ms for better planning and make it smarter; even if the whole
process takes a few seconds, that's better than something that doesn't work." Branch `cloud/planner-think` from
`main`, one PR, Python only.

## Hypothesis
Today the planner renders an empty `<think>\n\n</think>` block (non-thinking mode) and decodes the DSL directly.
Qwen3.5/3.6 are trained to reason in the think block; letting them reason for a bounded budget before the action
batch should raise holdout pass (multi-step order, picking the right ref, knowing when to ask/confirm/done) at a cost
of roughly 1–3 s per planner step on the Mac.

## Build (`ml/src/brain/planner.py` + CLIs)
- `Planner(..., think_budget=0)`. 0 = today's behaviour, byte-identical prompts (existing tests stay green).
  N > 0: open the assistant turn with `<think>\n` instead of the empty block, decode free text up to N tokens, then
  force-close with `\n</think>\n\n` if the model hasn't closed it, then decode the action batch with the existing
  line-start op constraint and done-alone rule applied **only after** `</think>`.
- The static-prefix cache must keep working (reasoning sits in the assistant turn, after the dynamic state).
- Decoding: keep greedy as one option and add Qwen's recommended thinking sampler as another (temperature 0.6,
  top-p 0.95, top-k 20, fixed seed), plus a repetition guard that closes the think block on a repeated n-gram loop.
- The reasoning never reaches the user; trace it as `planner.think` (first 400 chars, token count, ms).
- Variant flag `think_on="all"|"retry"`: `retry` thinks only when replanning after a failed `expect`, an action
  error or an ask/confirm reply.
- Works for the 4B planner and the 35B-A3B escalation planner.
- Flags: `brain serve --planner-think N --planner-think-on all|retry --planner-think-sampler greedy|qwen`,
  the same on `evals/planner_offline.py` and `evals/planner_v2_run.py`, and env `THINK`, `THINK_ON` in
  `tools/serve_brain.sh` (default 0 until the lead flips it).
- Tests with the existing fake tokenizer/model patterns: budget cut-off, constraint only after `</think>`, prompt
  identity at N=0, trace fields.

## Mac evaluation (the lead runs it; put exact commands in the PR body)
Matrix on v1-holdout, v1-holdout2, v2-holdout (v1-tune for reference), all with the shipped config
(few-shot, DSL history, constraint, done-alone, `RETRIEVAL_K=1`):
4B think ∈ {0, 256, 512, 1024} × sampler {greedy, qwen}, `think_on=retry` at 512, and 35B-A3B think ∈ {0, 512}.
Report pass, per-step latency p50/p95, mean think tokens.
Pre-registered ship rule: a config ships if mean holdout pass ≥ .672 (shipped .642 + 3 pts) with per-step p50 ≤ 3.0 s
on the Mac; among passing configs the highest holdout mean wins, ties go to the faster one.

No Tinker, no API spend.
