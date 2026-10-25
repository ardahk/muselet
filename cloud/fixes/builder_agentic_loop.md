# Lane: agentic-loop — planner keeps going until the goal's end state is visible

Read `cloud/builder_common.md` and `AGENTS.md` first. Branch `cloud/agentic-loop` off main (>= c405103), one PR,
Python only (`ml/src/brain/orchestrator.py`, `planner.py`, `plan_bank.py`, `finish.py`, tests). Deadline: open the
PR within ~90 min; push hourly.

Context (user live session, traces in the PR #87 description are summarised here):
- "Play some jazz music on Youtube": planner's `url "https://www.youtube.com/results?search_query=jazz+music"` with
  `expect title~"jazz"` failed because Zen's window title was still "Zen Browser" while loading (settle 1.7 s). The
  failure counted toward the 3-failed-turns loop guard and the planner started improvising (open Safari, type URL
  into the address bar, 404). Another run reached "jazz - YouTube" results but never clicked a video.
- Main now has: `finish.finish_when(goal)` appended as `Finish when:` to every planner turn; blind/open-ended tasks
  use the base planner with batch cap 2; done is not accepted from an `app "X"` expect unless the goal is a bare open.

Implement (each with unit tests using the existing fakes in `ml/tests/fakes.py` / `test_planner_loop.py`):
1. **Page-load re-poll.** When an action's expect fails and the observation shows a browser still loading (window
   title equals the browser name, or contains "Transferring data", "Loading", "Untitled", or observe returns
   `web_ax_pending`), re-run `verify {expect}` every 250 ms for up to 5 s before reporting failure. If it still
   fails in a loading state, report it to the planner as `[pending: page loading] ...` and do not count it toward
   the loop guard (at most one strike per task for loading failures).
2. **Done needs the finish criterion.** For goals where `finish_when` returns a play/cart/search/directions
   criterion, a `done` is only accepted with evidence: play → AX observation contains a button whose label matches
   `(?i)^pause\b` (YouTube "Pause (k)", "Pause keyboard shortcut k", Spotify) or the last script stdout contains
   "playing"; search → window title or URL contains the subject; cart → observation/OCR text matches
   `(?i)added to (?:your )?cart|cart subtotal|\b1 item`; directions → title/obs contains "Directions" or "Route".
   Otherwise reject done once with `done rejected: finish criterion not visible (<criterion>)` and replan (reuse
   the existing done-rejection/recovery path; keep VERIFY_DONE=off behaviour unchanged).
3. **Results page is not the end.** Regression: fake planner reaches a YouTube results page (`title "jazz - YouTube"`,
   no Pause button) and emits `done` → rejected; next turn it presses a video link → observation shows
   `button "Pause (k)"` → done accepted.
4. **Workflow-memory hygiene** (`_planner_memory_writes` + wherever workflows.jsonl is loaded into the plan bank):
   drop demos with < 2 actions, whose actions are all ref-based (`press #N`, `type #N ...`, `scroll #N`), or whose
   goal has < 3 words; write a workflow only when done was verified by evidence other than an `app` expect.
   Filtering at load is enough for the user's existing file; never delete it.
5. **Retrieval cross-app skip** (`planner.retrieval_block` / `PlanBank.retrieve`): when the goal names an app or
   site (`orchestrator.app_in` against installed names is not available here; use `sites.match_name` and the
   app-hint matcher `app_hints.match_hints`), skip demos whose goal names a different app/site, and fill k from
   the next candidates.
6. **Regression tests from the user traces:** "Play some music on YouTube" with ctx app "Devin" never emits
   `open "Spotify"` / `spotify:` (screen-context gate from #86 + item 5); the loading-title case above re-polls and
   doesn't strike the loop guard.

Gates: `uv run --project ml pytest ml/tests -q` and `bench/tests` must stay green. PR body: `## Handoff` + what
changed per item + test summary. Don't merge; the lead reviews and merges.
