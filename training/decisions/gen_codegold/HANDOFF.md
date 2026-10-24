## Handoff

_Cut-over snapshot 2026-10-24 (org credits ending). Lane: data-decisions (code-gold System One data). No Tinker usage in this lane, ever: training is owned by the decisions builder._

### State
- **Done**
  - 7 code-gold generators (`families/cg_{counting,multi_hop,long_policy,temporal,numeric,probability,trap}.py`), each with an independent `verify_rendered` and tests. The suite was green (52 passed) at f3e42f4.
  - Paraphrase stage, K=4 teacher labeling and decontam2 (13-gram, identical option sets, edit<=1 on short items). Decontam references: JevBench public 231, typed-decisions test 400, route_v1 140, live_t1 43, evals/external 570, route_v2 955.
  - Pilot: 105 states, 337 kept decisions.
  - First half of the full run (`full`, seed 2, 200/family):
    - 1,400 states generated, 1,395 kept.
    - 4,832 decisions labeled, 4,319 kept.
    - Decontam 0 hits.
    - Agreement: counting 81.0, long_policy 94.7, multi_hop 92.2, numeric 79.5, probability 95.9, temporal 88.4, trap 94.6.
- **In flight at cut-over:** second half `full2` (seed 3, 200/family).
  - gen and paraphrase are complete (1,400 states).
  - Labeling was partial at the snapshot: 871 states labeled, 3,048 label_results lines.
  - decontam for full2 has not been run.
- **Not started (no code yet)**
  - Merge full + full2 into `final/`.
  - `split` on the merged set.
  - `hard_codegold` config.
  - HF upload of the final dataset `jonsnov/muselet-decisions-v2`.
  - `REPORT.md`.
  - `run.py` `datums` stage (it raises NotImplementedError; not required, the training owner builds datums).

### Resume (about 10 min)
```bash
git fetch origin && git checkout cloud/data-decisions     # PR #38 -> cloud/decisions
uv venv ml/.venv --python 3.12 && uv pip install -p ml/.venv -e ml pytest pyarrow huggingface_hub httpx   # or: uv sync --project ml
# restore the run dirs (gitignored) from the private WIP snapshot
ml/.venv/bin/python -c "from huggingface_hub import snapshot_download as s; s('jonsnov/muselet-decisions-v2-wip', repo_type='dataset', revision='3de9c2e7fc1c3110ebf94ebdbd43fffe4f190c66', local_dir='.')"
mkdir -p data/bench/typed_decisions && cp runs/decisions/codegold/refs/typed_decisions_test.parquet data/bench/typed_decisions/test-00000-of-00001.parquet
git clone https://github.com/deskmind-ai/jevbench runs/bench/_src/jevbench && git -C runs/bench/_src/jevbench checkout 609a664e81f46e03731600bd7bd9f1b7a61257c5   # JevBench public refs (path used by decontam2.py); adjust URL if the remote differs
timeout 280 ml/.venv/bin/python -m pytest training/decisions/gen_codegold/tests -q -x
# 1. finish full2 labeling (resumable: skips decision_ids already in label_results.jsonl), then decontam
ml/.venv/bin/python -m training.decisions.gen_codegold.run label    --run full2 --seed 3 --per-family 200 --budget 33
ml/.venv/bin/python -m training.decisions.gen_codegold.run decontam --run full2 --seed 3 --per-family 200
```
Then the remaining steps, which need code:
2. **Merge** `full/decontam.jsonl` + `full2/decontam.jsonl` into `runs/decisions/codegold/final/`.
   - Dedupe by record id and by sha1(state); expect 0 duplicates.
   - Rerun decontam on the merged set; it must be 0.
   - Split per family 95/5 train/validation with seed 2.
3. **`hard_codegold` config.** Take the decisions that failed the teacher gate (`teacher_disagreements.jsonl`) where the family verifier passes on the final state and there were no API failures.
   - Target: 0.97 on the code gold, 0.03 spread evenly over the other options/levels, `label_basis: "code_onehot"`.
   - Main records get `label_basis: "teacher_k4"`.
   - One record per state; use the same split as main, assigned by state id.
4. **Upload** to a NEW private HF dataset `jonsnov/muselet-decisions-v2`.
   - Mirror the record schema and file naming of `jonsnov/muselet-decisions-v1` @ 9683da5aff5eea74749c3111186841e6d96d4d79, and do not touch v1.
   - Add `hard_codegold/` and a dataset card: additions only, generator sha, label settings, decontam result.
5. **`REPORT.md`** in this directory, with every number taken from the artifacts:
   - counts per family;
   - teacher agreement per family and per question kind;
   - gates: leak audit, schema parse, verifiers, position χ², score-level balance, decontam per reference;
   - paraphrase stats, spend, HF sha, known limitations.
6. Update PR #38 and this file, then reply to the lead. Expected totals: about 2,790 states and about 8,600 kept decisions.

### Artifacts
- Branch `cloud/data-decisions`, PR https://github.com/ardahk/muselet/pull/38. Commits: a7197ec (pilot pipeline), f3e42f4 (wording fixes), and this handoff commit.
- WIP run-dir snapshot: HF dataset `jonsnov/muselet-decisions-v2-wip` @ 3de9c2e7fc1c3110ebf94ebdbd43fffe4f190c66 (private). It holds `runs/decisions/codegold/{full,full2,pilot,refs,gen_cost.jsonl}` plus the typed-decisions test parquet.
- Final HF dataset: not created yet. Tinker: none.

### Spend
- **$29.51 of the $70** (ledger `gen_cost.jsonl`, sum of `cost_usd`). This covers the pilot ($2.56), full ($14.50) and the partial full2.
- Remaining full2 labeling is about $4, so the projected total is about $33.

### Open questions for the lead
- Should the `hard_codegold` config (one-hot + ε=0.03, teacher-gate failures with verified code gold) ship next to the SPEC-gated main config? It was proposed and is not yet confirmed.

### Gotchas
- Use `ml/.venv/bin/python` (pytest lives there); a venv without torch fails test collection.
- `gen` reseeds the RNG from `--seed`, so a new chunk needs a new `--run` dir AND a new seed, or it regenerates duplicates.
- `run.py::_ledger`: `--budget` is the per-round cap and `cumulative_budget` is hard-coded (keep the project under $70). The ledger file keeps growing, so do not delete it.
- Teacher is gpt-5.4-nano, reasoning low, K=4. Paraphraser is gpt-5.4-mini. Prompts are in `common.py`/`run.py`. About 50% of paraphrases are rejected by the preservation/verifier gate, which is expected.
- Hand-checked disagreements had correct code gold: nano misses "strictly before" deadlines, relative-change direction and rule-scoped totals.
- The typed-decisions parquet in the HF repo is under `all/test-*.parquet`, not `test/`.
- route_v2 ref: `git show origin/cloud/data-pipeline:evals/route_v2.jsonl` (also in the snapshot under `refs/`).
