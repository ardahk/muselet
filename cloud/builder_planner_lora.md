# Lane: planner-lora — SFT the 4B planner on the gated teacher demos (Tinker, ≤ $7 total)

Brief of record: `cloud/handoff/W4_planner.md` step 3. Branch `cloud/planner-lora` from `main`, one PR.

## Why (hypothesis)
The shipped planner is base `mlx-community/Qwen3.5-4B-4bit` + `prompts/planner_fewshot.md` + DSL history +
line-start constraint + done-alone + 1 BM25-retrieved example (`RETRIEVAL_K=1`). Holdout pass: v1-holdout .714
(10/14), v1-holdout2 .750 (9/12), v2-holdout .462 (60/130), mean .642 (`cloud/handoff/notes/retrieval_eval.md`).
Expected: SFT on validator-passed teacher demos teaches the DSL, `expect` use and the hard categories (Finder files,
permission prompts, sign-in pages, web answers) better than in-context examples: + holdout pass, possibly with a
shorter prompt (no few-shot block → faster TTFT).

## Data
`jonsnov/muselet-planner-demos-v1` @ `9453ff6` (1,194 demos, both teachers had to pass the grader), tooling in
`training/planner_demos/` (read its `HANDOFF.md`). Re-run the contamination gate against v1 tune/holdout/holdout2,
`evals/planner_scenarios_v2.jsonl` v2-holdout, `evals/live_t1.jsonl`, HobbyLM sealed r1–r4 and DeskMind
diag/dyn/proposals (exact, shared 13-gram, short-item edit ≤ 1, CJK-aware). It must be 0; table in the PR.
Hold out 5% of demos (seed 0) as dev for checkpoint selection. Never select on any eval set.

## Training (settled)
- Render each demo **exactly** as `ml/src/brain/planner.py` builds the serving prompt (system prompt, DSL history,
  dynamic observation state) **without** the few-shot block and without retrieved examples; target = the demo's
  action batch. Qwen3.5 chat template with the empty think block, loss on assistant tokens only. Prove token-level
  parity on 20 samples against the brain's own prompt builder (a test).
- LoRA rank 32, LR 2e-4, batch 32, cosine decay, checkpoints every 25% of the run, keep all.
- **Cost first:** count tokens in a dry run and post the estimate (~$0.78 per million training tokens). Run 2 epochs
  if the whole lane fits in $7, else 1 epoch. Abort before launching if `python3 tools/tinker_spend.py` or the
  console shows month-to-date ≥ $142, and stop sampling at $146.
- Pick the checkpoint on dev: validator pass rate of greedy samples (Tinker sampler, small) and dev loss.

## Export and Mac handoff
- MLX 4-bit export with the **untied lm_head** (same procedure as the router exports; see `docs/REPORT.md`) → new HF
  repo `jonsnov/muselet-planner-4b-lora-mlx4`. Never touch other repos.
- Serving needs nothing new: `PLANNER=<local path> tools/serve_brain.sh` plus the few-shot flag. Write the exact
  Mac commands in the PR body for the lead's tuned-vs-tuned matrix, each on v1-holdout, v1-holdout2, v2-holdout
  (and v1-tune for reference): LoRA without few-shot (k = 0 and 1), LoRA with few-shot + k = 1, vs the shipped base
  config. Use `evals/planner_offline.py` and `evals/planner_v2_run.py`.
- Pre-registered ship rule (the lead applies it on the Mac): a LoRA config ships if mean holdout pass ≥ .672
  (shipped .642 + 3 pts), no holdout set drops by more than 1 scenario vs shipped, and TTFT p50 ≤ shipped + 50 ms.

API cap: $5 per provider (you should need none).
