# Cloud builder: brain follow-ups (Python only) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first (contracts), then `ml/src/brain/{orchestrator,planner,decision,dsl,
server,cli,catalog}.py`, `ml/tests/test_planner_loop.py`, `ml/tests/test_orchestrator.py`, `skills/catalog.json`,
`cloud/tools_interface.md`. Muselet is a fully on-device macOS voice agent; the brain (Python, MLX) routes an
utterance in one forward pass (~55 ms, Qwen3.5-4B) to a native skill, a brain tool, or the System-2 planner, and
drives the Mac through HandsKit RPCs over a WebSocket. Goal: speed first, then accuracy, then task complexity.

Work on branch `cloud/brain-2` from `main` (planner landed in 17a2755), one PR. You own
`ml/src/brain/{orchestrator,planner,decision,server,cli}.py` and may add new modules/tests under `ml/`. Do not
edit `app/`, `skills/catalog.json`, `prompts/`, `evals/`, `ml/src/brain/{finance,advisor}/`, or
`ml/src/brain/tools/{finance_review,advisor_prep}.py` (other agents own them). No API keys needed.
Environment: this VM is Linux. Try `uv sync --project ml`; if mlx/mlx-lm cannot install, run the tests that don't
need model weights (all of the ones below must not) and report which tests need the Mac. Never edit
`ml/pyproject.toml` pins without saying why in the PR.

## Tasks
1. **Missing required args -> recover, don't fail.** Live failure: "make a new note that says buy milk" -> ARGS
   gave only `title`, `body` is required, the skill failed.
   - First a small per-skill fallback table in code (tested): `new_note`: body <- title when body is missing
     (title then = first 6 words of body); `create_reminder`/`create_event`: title <- the utterance minus the
     datetime phrase when title is missing; extend only with obviously safe cases.
   - Otherwise slot-fill: `say` a natural question per arg ("What should the note say?", "Who should I text?",
     "When?"; <= 12 words), keep `{skill, args, missing, t}` for 60 s, and treat the next final utterance as the
     value (coerced by type), then execute. A different-looking command (router p_top >= 0.8 for another skill)
     cancels the slot and runs normally. Trace `slot_fill: true`.
2. **Planner turns reuse act diffs.** Today `_planner_loop` calls `observe` every turn. Add `ml/src/brain/obsdiff.py`
   with `apply_diff(obs_text, diff_text) -> str` for the AGENTS.md formats (`+ #31 button "Export"`, `- #7`,
   `~ #4 value="hel"`; header line kept). In the loop, when the last act result carried `diff_text` (non-empty or
   empty) and not `full`/`truncated`, build the next observation from it instead of a fresh `observe`; otherwise
   observe. Unit-test apply_diff thoroughly (add/remove/change, refs absent, header updates) and a loop test that
   asserts no observe RPC between turns when a diff is available.
3. **Exact answers by code.** ANSWER currently asks the model. Add `ml/src/brain/calc.py`: deterministic answers for
   percentages ("15 percent of 80", "what's 18% tip on 64.50"), basic arithmetic in words or digits, and common unit
   conversions (lb/kg, oz/g, mi/km, ft/m, in/cm, F/C, cups/ml, tbsp/ml), with spoken-number parsing. If it parses,
   `say` the result (<= 12 words) without calling the model; else fall back to the model. 40+ unit tests.
4. **Latency report.** `brain trace-stats [--since ISO] [--path runs/traces]`: p50/p95 of
   `release_to_first_action_ms`, `route_ms`, `args_ms`, planner TTFT, decode tok/s, total ms, grouped by outcome and
   by route label/skill, plus spec_hit rate and slot_fill count. Test on a small committed fixture trace file.
5. **Partial-utterance speculation, step 2.** Speculation currently routes only. When the speculative route is a
   skill with p_top >= tau, also speculate ARGS on the same worker (cancel/ignore if the partial changes); reuse on
   final when the normalized text matches. Tests with a fake engine.
6. **Confirm summaries.** Make sure every confirm summary names the object (recipient + first words of body, file
   name, app) and stays <= 12 words; tests.

Quality bar: every behavior change has a test; keep the code compact and in the existing style; no new
dependencies. Reply with the PR link, the test counts, which tests need the Mac, and any deviation.
