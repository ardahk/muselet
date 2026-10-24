# W9 safety backlog: handoff (WIP)

Branch `cloud/w9-safety`, based on main `83c1f21`. Brief: `cloud/handoff/W9_safety_backlog.md`.

## State
- **Done:** every W9 item re-verified against main `83c1f21` by reading the code and the reviewer findings and repros
  (origin/review/{brain,evals-safety,hands}). The results are below.
- **In flight:** nothing. No code changes are committed yet, and no PR is open.
- **Not started:** all fixes and their regression tests.
- Spend: $0 (no Tinker or HF use).

## Per-item verdict on main 83c1f21 (line numbers are in ml/src/brain/orchestrator.py unless noted)
1. **Script confirm (evals-safety-2/-22, brain-9): partly open.** The real gate is the method
   `Orchestrator.script_needs_confirm` (:2066), called at :1704 (planner `_exec_one`) and :2782 (`_script`). The
   module-level `script_needs_confirm` + `_DANGEROUS_SCRIPT` (:31, :369) are dead code with a weaker regex, and only
   `ml/tests/test_orchestrator.py:283` imports them (es-22). Delete them and point that test at the method.
   Bypasses I found by reading `_SCRIPT_BLOCK` (not yet proven with tests):
   - `tell application "Safari" to open (POSIX file "/tmp/x.html")`: the parenthesis defeats `open\s+(?:POSIX\s+)?file`.
   - `do  shell script` (two spaces), or an `¬` line continuation: the regex uses literal single spaces. Normalize
     `¬\n` and runs of whitespace before matching.
   - JXA camelCase forms are not matched: `doJavaScript`, `openLocation`, `keyCode`, `makeNew`/`.make(`, `doScript`.
     Only `doShellScript` is.
   - System Events UI scripting with `select`, `increment`, `decrement` or `pick` is not blocked (System Events is in
     `_SCRIPT_APPS_READ`). The brief says System Events UI scripting must confirm, so any `process "..."` /
     `processes` reference under System Events should confirm.
   - Targets are collected only from `tell application "X"` (and JXA `Application("X")` when there is no tell). A bare
     `application "Terminal"` reference elsewhere is ignored. Collect every `app(lication) "X"` / `id "X"`.
   - ASObjC: `current application's NSTask`/`NSWorkspace`, `use framework`: only `NSFileManager`/`ObjC` are matched.
   - JXA computed keys and escapes (`app["del"+"ete"]()`, `\u0064elete`, `String.fromCharCode`, `eval`, `Function(`).
   - ASCII raw events `<<event coredelo>>`: only the `«event` form is matched.
   - Keep the narrow Numbers `make new table` exemption (it has a test: test_planner_loop.py:389-395). The brief says
     "make new" must always confirm, so this is an open question for the lead.
2. **Done trusted (evals-safety-11, brain-11): partly open.** The 5th action's expect is kept (BatchCutter,
   ml/src/brain/planner.py:132-150), so that part is resolved. In the planner loop, done is accepted at :2380-2393 when
   `n_executed==0 and (prev_expect_ok or obs_fresh and (not prev_had_failure or done_rejected))`. A fresh
   observation with no prior failure, or any second done after one rejection, is accepted on the model's word alone.
   Plan:
   - Accept done only if the previous batch's last expect passed, or done carries its own `expect` (the DSL already
     attaches `expect` to the previous action, done included) that passes a `verify` RPC.
   - Otherwise reject with `done -> failed: needs evidence (add expect <predicate>)`.
   - On a second rejection return `"unverified"`, the idle mascot (as execute_actions already does at :2689),
     never `"ok"`.
3. **One confirm unlocks batch (brain-14): open.** `_take_confirm` (:1998) is consumed only by a dangerous action,
   and harmless actions do not clear the token. Repro: origin/review/brain
   `reviews/brain/tests/test_brain_pass16.py::test_brain14_confirm_not_carried_over_harmless_action`.
   Fix: clear `self._batch_confirmed` after every non-`confirm` action in `_exec_one`, so a model confirm covers only
   the immediately following action.
4. **YesNo (hands-2): resolved by reading.** `app/Sources/HandsKit/YesNo.swift` maps any negator anywhere to false,
   so "not right now" (`not`) and "ok cancel" (`cancel`; `ok` is filler) both come out false. Tests are at
   `app/Tests/HandsKitTests/ReviewFixesTests.swift:153-181`. The literal "ok cancel" case is missing; add it on a Mac
   (`swift test --scratch-path .build-hands`). I did not compile it here (Linux box).
5. **Calculator wrong app (brain-25): open.** `_deliver_calc` sends `act {op:open, app:Calculator}` with no
   expect, and `Act.swift:424-431` discards `waitFrontmost`'s result. Fix: add `expect: 'app "Calculator"'` to the open
   act and abort before any key if `expect_ok` is False, the act fails, or a returned `app`/diff shows another app.
   Repro: `test_brain_pass24.py`.
6. **Fuzzy trash path (brain-24): open; confirm-path half verified.** `pathfind.resolve` accepts a
   SequenceMatcher ratio of 0.88 or more, so `invoice 2024` resolves to `invoice 2023.pdf`, and `_run_skill`
   (~:837-880) auto-picks a single match. The confirm summary does show the full path (`_confirm_summary` :1513-1519).
   Fix: require the digit sequences to match exactly in resolve; for `move_to_trash`, auto-pick only an exact
   normalized match and send fuzzy hits to the "Which one: …?" slot. Repro: `test_brain_pass20.py`.
7. **35B escalation race (brain-30): open.** `set_escalation` (~:2100) is not serialized. Repros:
   `test_brain_pass34.py::test_brain30_*`. Fix: an `asyncio.Lock` plus a desired-state flag. A disable that arrives
   during a load sets desired=False without waiting; the load then discards its planner. Re-check memory inside the
   lock.
8. **Sites rewrite (brain-29): open.**
   - `_app_names` (~:921) caches `[]` for 60 s when the RPC fails.
   - `_installed_app_keys` normalizes file names, so `zoom.us`, `Microsoft Teams` and `Microsoft Outlook` never
     match `zoom`/`teams`/`outlook`.
   - Three call sites need one shared helper: `_rewrite_app_skill`, `_exec_one` op `open` (~:1765) and
     `execute_actions` op `open` (~:2700).
   - Fix: a native-app alias table; don't cache a failed RPC and don't rewrite when the installed list is unknown;
     explicit "website / go to / navigate / .com" wording forces the URL.
   - Repros: `test_brain_pass34.py::test_brain29_*`.
9. **`appears` scope (hands-12 residual): open, Swift.** In `app/Sources/HandsKit/Expect.swift`, `Expect.eval` uses
   `localizedCaseInsensitiveContains` (a substring match), and the `searchLabel` fallback walks every window of the
   app. Fix: a word-bounded or exact label match, and limit the fallback to the target window plus its
   sheets/popovers and any open menu. Needs a Mac compile.

## Resume steps
```
cd ml && uv sync            # uv was not on this box; install: curl -LsSf https://astral.sh/uv/install.sh | sh
uv run pytest -q tests      # baseline
git show origin/review/brain:reviews/brain/tests/test_brain_pass34.py > /tmp/rt/test_brain_pass34.py  # etc
PYTHONPATH=src:tests uv run pytest /tmp/rt/test_brain_pass16.py::test_brain14_confirm_not_carried_over_harmless_action \
  /tmp/rt/test_brain_pass20.py /tmp/rt/test_brain_pass24.py /tmp/rt/test_brain_pass34.py
```
Suggested PRs (2-3 items each): A = items 1+3 (confirm policy); B = 2+5+6 (verification / wrong target);
C = 7+8 (escalation + sites); D = 9 (+ the YesNo test) on a Mac.

## Open questions
- Keep the Numbers `make new table` script exemption (item 1)?
- After two done rejections: should the result be `unverified` (my plan) or a hard fail?

## Gotchas
- The findings jsonl files are append-only; the digest.md of each lane holds the current open list. The review
  repros live only on origin/review/brain (`reviews/brain/tests/`) and import `ml/tests` helpers
  (`PYTHONPATH=ml/src:ml/tests`).
- Linux test venv: `uv sync --group dev` alone fails at `import mlx.core` (libmlx.so missing); then
  `uv pip install 'mlx[cpu]==0.32.4'` fixes it. Baseline on 83c1f21: `uv run pytest -q tests` -> 1453 passed, 55 skipped.
  Reviewer repros (`PYTHONPATH=$PWD/tests:/tmp/rt uv run pytest -q /tmp/rt`): 37 failed / 26 passed; brain-14/24/25/29/30
  repros fail, brain-9 passes.
