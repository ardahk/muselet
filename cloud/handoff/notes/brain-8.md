# Handoff: brain-8 (fixes from the first valid live run)

## State
- **Done and merged.** PR https://github.com/ardahk/muselet/pull/32 (branch `cloud/brain-8`, commit `4546d09`).
  The lead followed up on main with review commit `9a47376`: TCC phrases now need a decision button in every
  app, not just browsers, and the pathfind test works on case-insensitive APFS.
  - P0 permission-prompt gate: `orchestrator.permission_prompt()` and `_permission_gate()`, checked in the
    planner loop (before `plan()`), `_exec_action`, `execute_actions` and `_skill` (input skills). "continue"
    resumes the parked goal.
  - P0 absolute folder paths: `pathfind.absolute()`, `PATH_ARGS`, `_run_skill` normalization, `_skill` final
    guard ("Which folder should I use?").
  - P1 degree words beat the model delta: `argfix.degree_delta()` in `_run_skill`.
  - P1 web question answers: `_web_answer()`, `question_like()`, `WEB_ANSWER_SYSTEM`; stages
    `web_answer.observe` and `web_answer.generate`.
  - Tests: `ml/tests/test_brain8_live_fixes.py` (85 tests, fakes only).
- **In flight:** nothing.
- **Not started:** live Mac verification of the four fixes with `bench/live/run_live.py` (t2-downloads-list,
  folder cases, sys-vol-up-lot, web-question case).

## Resume steps
```bash
git clone https://github.com/ardahk/muselet.git && cd muselet
curl -LsSf https://astral.sh/uv/install.sh | sh && export PATH="$HOME/.local/bin:$PATH"
# Linux only (no Metal): MLX CPU wheel so the brain imports
uv pip install --project ml mlx-cpu==0.32.4   # or: uv run --project ml pip install mlx-cpu==0.32.4
uv run --project ml python -m pytest ml/tests -q      # at PR time: 1290 passed, 55 skipped
uv run --project ml python -m pytest bench/tests -q   # 162 passed, 2 skipped, 38 subtests
uv run --project ml python -m pytest ml/tests/test_brain8_live_fixes.py -q
# On the Mac: bench/live/run_live.py (see AGENTS.md LIVE-TEST SAFETY)
```

## Artifacts
- Commits: `4546d09` (brain-8 PR #32), `9a47376` (lead's review follow-up on main).
- No HF repos, Tinker runs, checkpoints or run dirs. This lane is code-only.

## Spend
- No Tinker, HF or API spend. The only cost is Devin session time.

## Open questions
- `find_file.scope`: `skills/catalog.json` has no `scope` arg, so a model `scope` is normalized and then
  rejected by `validate_args`. Supporting it needs a catalog and HandsKit change.
- The gate costs one extra `observe` RPC in `execute_actions` and the input skills (`type_text`,
  `copy_selection`, `premiere_command`) when nothing was observed during that utterance. Routed non-input
  skills (open_app, set_volume, ...) are not gated. Should they be?
- `~` is expanded to `$HOME` before the RPC, so HandsKit always receives `/Users/<u>/...`.
- `question_like` is a regex heuristic. "look up pasta recipes" stays a plain search.

## Gotchas
- Linux test runs need `mlx-cpu`; otherwise collection fails with `libmlx.so: cannot open shared object file`.
- `uv` isn't preinstalled on the cloud VMs.
- No `prompts/` or `evals/` edits; the lead owns them. Gates go in code, and the planner prompt text stays
  unchanged.
- The gate's fresh observe sets `_last_epoch`, so later acts carry `epoch`. Tests that compare exact act params
  should match on op/combo instead.
