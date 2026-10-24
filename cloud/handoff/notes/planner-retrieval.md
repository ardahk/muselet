## Handoff
_Cut-over 2026-10-24. Lane: planner-retrieval. Code in main via #35 (feature commits 3717f02, 9786fa4; note 7df32b1; merge 537c4dd). This note: PR #41, branch `cloud/planner-retrieval-handoff`._

**State**
- Done: BM25 retrieval of 1-2 solved examples per planner request. It is opt-in (`Planner(retrieval_k=0)`, `brain serve --planner-retrieval-k`, `evals/planner_offline.py --retrieval-k`, `evals/planner_v2_run.py --retrieval-k`), in `main`, and off by default. The report and decision script is `evals/planner_retrieval_report.py`. Tests: 20 new; the full `ml` suite is 1315 passed, 55 skipped (Linux, mlx-cpu).
- In flight: nothing. No jobs are running and there is no uncommitted work.
- Not started: the real model evaluation on the Mac (k=0/1/2 × 4 sets). The ship/no-ship decision depends on it, and so does any default flip.

**Resume (Mac, Apple Silicon, one model process at a time)**
```bash
git checkout main && git pull && (cd ml && uv sync)
M=mlx-community/Qwen3.5-4B-4bit
C="--model $M --constrain --done-alone --history dsl --system-extra prompts/planner_fewshot.md"
for k in 0 1 2; do
  for s in tune holdout holdout2; do
    uv run --project ml python evals/planner_offline.py $C --set $s --retrieval-k $k --tag ret-k$k-v1$s
  done
  uv run --project ml python evals/planner_v2_run.py --v2-set v2-holdout $C --retrieval-k $k --tag ret-k$k-v2holdout
done
uv run --project ml python evals/planner_retrieval_report.py --prefix ret   # table + DECISION
```
- Post the table and the DECISION line on a new PR or issue.
- If the DECISION is k>0, open a separate PR that changes the `--planner-retrieval-k` default in `ml/src/brain/cli.py`. Otherwise leave it at 0.
- Optional exploratory run (does not count toward the decision): the same loop with `--retrieval-bank hf@9453ff6`, tags `rethf-k$k-...`, report `--prefix rethf`.

**Pre-registered decision rule** (`planner_retrieval_report.decide`): ship k>0 only if all three hold vs k=0:
1. The unweighted mean pass rate over v1-holdout, v1-holdout2 and v2-holdout gains ≥ 0.03.
2. No set among the four loses more than 1 passing scenario.
3. TTFT p50 rises by ≤ 150 ms on every set.

If both k=1 and k=2 pass, take the larger gain; on a tie, take k=1. Never tune on the holdouts.

**Artifacts**
- Commits on main: `3717f02` (feature), `9786fa4` (HF .gz/@rev loader, chrome filler), `7df32b1` (handoff note).
- HF dataset `jonsnov/muselet-planner-demos-v1@9453ff6` (private; `bank.jsonl.gz`, 1194 rows, 1193 after the denylist). It is produced by `training/planner_demos/` (PR #33).
- Default bank: `split == "v2-tune"` rows of `evals/planner_scenarios_v2.jsonl` (130 rows, 129 kept).
- Tinker: none (no run ids or checkpoints). Run dirs: none yet. Outputs will land in `runs/planner_offline/<tag>.json`.

**Spend:** $0 in API, Tinker or GPU. Only HF downloads.

**Open questions for the lead**
- Should the HF bank count toward the decision? Currently it does not, because its rows have only the window header, no element lines.

**Gotchas**
- Linux tests: `uv pip install mlx-cpu==0.32.4` (otherwise `libmlx.so` ImportError), then `cd ml && uv run --no-sync pytest tests/test_plan_bank.py tests/test_planner_retrieval.py tests/test_planner_flags.py`. The live HF test skips without `HF_TOKEN`.
- The report requires all four k=0 runs and skips any k>0 config with a missing set. Tags must match `ret-k{k}-v1tune|v1holdout|v1holdout2|v2holdout`.
- `planner_v2_run.py` takes `--v2-set`, never `--set`.
- Bench `ttft_ms` includes retrieval time (`retrieval_ms` is also logged per row).
- The leak filter drops v2-tune `v2-mail-no-account` ("check my email" is 1 edit from the denied "check my gmail"). This is expected.
- The HF bank schema (`header`, string `batch`) is aliased in `plan_bank.load_jsonl`. BM25 on HF demos leans on window-header tokens.
- The 35B escalation planner gets no retrieval.
- Forbidden edits for this lane: `prompts/planner_system.md`, `prompts/planner_fewshot.md`, the v1/v2 scenario files.
- The repo has no CI.
