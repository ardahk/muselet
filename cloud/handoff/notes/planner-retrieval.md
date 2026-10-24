## Handoff
_Updated 2026-10-24 (planner-retrieval lane, PR #35)._

**State**
- Done: the code, tests and PR (ardahk/muselet#35, `cloud/planner-retrieval`, open, not merged). The repo has no CI.
- Not run: any real model evaluation. Linux has no Metal, so pass rate and TTFT for k=0/1/2 are unknown. Nothing is in flight.

**Next steps (Mac, Apple Silicon, one model process at a time)**
1. `git checkout cloud/planner-retrieval && cd ml && uv sync && cd ..`
2. Run the 12-run loop from the PR body section "Offline evaluation" (k=0/1/2 × v1-tune, v1-holdout, v1-holdout2, v2-holdout). Use tags `ret-k{k}-v1tune|v1holdout|v1holdout2|v2holdout`. Runs land in `runs/planner_offline/<tag>.json`.
3. `uv run --project ml python evals/planner_retrieval_report.py --prefix ret` prints the table and the DECISION. Paste it into the PR.
4. If the decision is k>0: a separate PR flips the `brain serve` default (`--planner-retrieval-k` in `ml/src/brain/cli.py`). Otherwise leave it at 0. Do not retune anything on the holdouts.
5. Optional, exploratory, does not count toward the decision: the same loop with `--retrieval-bank hf@9453ff6`, tags `rethf-k{k}-...`, `--prefix rethf`.

**Artifacts**
- Branch `cloud/planner-retrieval`. Code commits `3717f02` (feature) and `9786fa4` (HF gz/@rev + chrome filler); later commits only touch this note.
- HF dataset `jonsnov/muselet-planner-demos-v1@9453ff6` (private, from PR #33; file `bank.jsonl.gz`, 1194 rows, 1193 after the denylist).
- Default bank: `split == "v2-tune"` rows of `evals/planner_scenarios_v2.jsonl` (130 rows, 129 kept).
- No Tinker runs. No run dirs yet.

**Spend:** $0 in API, Tinker or GPU (only HF downloads).

**Open questions for the lead**
- Should the HF bank count toward the decision? Currently it does not, because its rows lack element lines.

**Gotchas**
- Linux tests need `uv pip install mlx-cpu==0.32.4` (otherwise `libmlx.so` ImportError), then `cd ml && uv run --no-sync pytest tests/test_plan_bank.py tests/test_planner_retrieval.py tests/test_planner_flags.py`.
- The live HF test in `test_plan_bank.py` skips without `HF_TOKEN`.
- The `report` script requires all four k=0 runs. A k>0 config with any missing set is skipped.
- `planner_v2_run.py` takes `--v2-set v2-holdout`, never `--set`.
- Edit-distance leak filter drops v2-tune `v2-mail-no-account` ("check my email" vs denied "check my gmail"). This is expected.
- HF bank rows: `header` + string `batch` (aliased in `load_jsonl`). They have no obs lines, so BM25 leans on the window header.
- The escalation (35B) planner gets no retrieval.
- Forbidden edits: `prompts/planner_system.md`, `prompts/planner_fewshot.md`, v1/v2 scenario files.
