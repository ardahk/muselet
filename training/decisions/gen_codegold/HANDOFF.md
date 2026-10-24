## Handoff

_Last updated: 2026-10-24 (second half of full run in flight)._

**State**
- Done: 7 code-gold generators (`families/cg_*.py`) with independent re-parse verifiers and tests (`tests/`, green at f3e42f4),
  paraphrase stage (lead-authored prompts, gpt-5.4-mini, preservation + verifier gate), decontam2 (13-gram, option sets,
  edit<=1 short items) against JevBench public 231, typed-decisions test 400, route_v1 140, live_t1 43, evals/external 570,
  route_v2 955 -> 0 hits so far. Pilot (105 states) and first half (`runs/decisions/codegold/full`, 1,395 states,
  4,319 kept decisions) complete.
- In flight: second half `--run full2 --seed 3 --per-family 200` (gen + paraphrase done, labeling running), then merge,
  split, hard subset, HF upload, REPORT.md.

**Next steps (exact)**
1. `ml/.venv/bin/python -m training.decisions.gen_codegold.run label --run full2 --seed 3 --budget 33` (resumable), then `decontam` same args.
2. Merge `full` + `full2` -> `runs/decisions/codegold/final/` (dedupe by id and sha1(state); expect 0 dups); rerun decontam (must be 0);
   split per family 95/5 seed 2.
3. `hard_codegold` config: decisions that failed the teacher gate, verifier-passing, no API failures; target one-hot 0.97 on
   gold, 0.03 spread over the rest; `label_basis: code_onehot` (main records: `teacher_k4`); same split by state id.
4. Upload to NEW private `jonsnov/muselet-decisions-v2` mirroring v1's layout (v1 @ 9683da5 untouched); additions only; dataset card.
5. Write `training/decisions/gen_codegold/REPORT.md` from artifacts (counts per family, agreement tables, gates, spend, HF sha).
6. Update PR + this file; hand over to the lead. Never start Tinker runs (training is owned by session 83651a51).

**Artifacts**
- Branch `cloud/data-decisions` (PR -> `cloud/decisions`); generator commit f3e42f4.
- Run dirs (gitignored, on the builder VM): `runs/decisions/codegold/{pilot,full,full2,final}`; ledger `runs/decisions/codegold/gen_cost.jsonl`.
- HF: `jonsnov/muselet-decisions-v2` not created yet. Tinker: none (out of scope).

**Spend**: $28.39 of $70 (ledger sum at last update: paraphrase $7.43, nano labels $20.96). Projection at completion ~$33.

**Open questions for the lead**
- OK to ship the `hard_codegold` (one-hot + eps) config next to the SPEC-gated main config? Proposed, not yet confirmed.

**Gotchas**
- Test/runtime env is `ml/.venv/bin/python` (pytest 9.1.1 there); `~/venv` lacks torch.
- `gen` reseeds the RNG from `--seed`: a new chunk needs a new `--run` dir AND seed, or it regenerates duplicates.
- Ledger cap: `--budget` is per round; cumulative cap hard-coded 66-68 in `run.py::_ledger` to keep the project < $70.
- Typed-decisions test parquet lives at `all/test-00000-of-00001.parquet` in the HF repo (copied to `data/bench/typed_decisions/`).
- route_v2 ref: `git show origin/cloud/data-pipeline:evals/route_v2.jsonl > runs/decisions/codegold/refs/route_v2.jsonl`.
- JevBench clone: `runs/bench/_src/jevbench` @ 609a664e81f46e03731600bd7bd9f1b7a61257c5.
- About 50% of paraphrase attempts are rejected by the preservation/verifier gate; that is expected and costs ~$0.005/state.
