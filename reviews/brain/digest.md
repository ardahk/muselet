# Brain lane review: pass 92 (2026-10-25T12:10Z)

Open: P0 0, P1 16, P2 32. New: brain-77 (P2, wip/local).

## Branches
- main 2de65a9 and cloud/cool-tasks cfbec49: unchanged.
- wip/local a6035fb: adds a2004d9, removing the finance/advisor engines; app intents always go to the planner and --agentic-apps is ignored.

## New
- brain-77 (P2, wip/local): suite goes from 18 to 106 failures; the 88 new ones include Premiere named-confirm, send-confirm and confirm-denied tests. The send_message and premiere_command confirm blocks in _exec_action are now unreachable.

## Notes
brain-57 opt-out removed. serve_brain.sh base planner now defaults to no few-shot and no retrieval (differs from its documented reference config).

## Tests
wip/local 106 failed (18 MLX-only + 88 new), 2197 passed. Review repros 77 / 53 (unchanged).

# Brain lane review: pass 91 (2026-10-25T11:40Z)

Open: P0 0, P1 16, P2 31. New: brain-76 (P2, wip/local).

## Branches
- main 2de65a9 and cloud/cool-tasks cfbec49: unchanged.
- wip/local 4db92e8: now carries 5 local commits ahead of main (page-load signal and waits, fused-expect stripping, Numbers sort guard, progress wording).

## New
- brain-76 (P2, wip/local): `wait <ms>` in a browser returns after ~150 ms when the page already reports loaded; waits for in-page updates are cut short. Repro test_brain_pass91.py (1500 ms -> 152 ms).

## Notes
Every press / Return in a browser now costs one extra observe; failed expects on a loading page can repoll for 15 s at 0.1 s. brain-73 unchanged.

## Tests
wip/local 18 MLX-only suite failures (same set as main), 2560 passed. Review repros: wip/local 77 / 53.

# Brain lane review: pass 90 (2026-10-25T11:12Z)

Open: P0 0, P1 16, P2 30. No new IDs; brain-73 widened.

## Branches
- main 2de65a9: 4bf7a41 refuses cmd+L/cmd+T in browsers and reads more cart-count labels; 36422a7 soft expects for every agentic app task.
- wip/local 5b70519: snapshot on main; lane identical.
- cloud/cool-tasks cfbec49: unchanged.

## Rechecked
- brain-73 (P1) widened: failed expects now return ok on any agentic app task, even without a finish criterion. New repro test_brain_pass90.py fails on 2de65a9, passes on 298526d.
- brain-67 context: the new cmd+L refusal is _no_strike, so repeats skip the loop guard.
- Everything else unchanged.

## Tests
main 18 MLX-only suite failures, 2529 passed. Review repros: main 76 / 53.

# Brain lane review: pass 89 (2026-10-25T10:58Z)

Open: P0 0, P1 16, P2 30. No new findings.

## Branches
- main 298526d: 8512116 think sampling with GPU top-k (sample_row) plus prefill_ms/prompt_tokens in think meta; 3c59fdc MUSELET_NO_ESCALATE=1 ignores the app's 35B toggle. Swift observe change outside the lane.
- wip/local d409a32: snapshot on main; lane identical.
- cloud/cool-tasks cfbec49: merges main through e2aa40c; carry unchanged.

## Verified
sample_row matches sample_logits in distribution (same support, TV 0.007 over 60k draws; greedy = argmax). Notes: seeded think samples change across this commit; prompt_tokens counts only the post-cache dynamic prompt.

## Rechecked
All open findings unchanged; repro failure sets identical to pass 88.

## Tests
18 MLX-only suite failures (main 2528, cool-tasks 2544 passed). Review repros: main 75 / 53, cool-tasks 75 / 53.

# Brain lane review: pass 88 (2026-10-25T10:42Z)

Open: P0 0, P1 16, P2 30. New: brain-75 (P2).

## Branches
- main 430e59e: c104e8b premiere agentic route with {} args, 35b defaults RETRIEVAL_K=0/THINK=1024; 69e6fa9 style `about` composed by the model. Swift Observe/Act changes are outside the lane.
- wip/local 9f6aa0d: snapshot on main; lane identical.
- cloud/cool-tasks 2fafa9e: merges main through 2dda1fb; brain-74 and brain-75 now on it; carry unchanged.

## New
- brain-75 (P2, main + cool-tasks): any <=5-word `about` containing funny/polite/short/nice/kind/... is treated as a style, so literal replies like 'thanks, that is very kind' or 'running short today' are paraphrased instead of typed. Repro test_brain_pass88.py 3/3.

## Rechecked
brain-66 partly addressed (short style abouts only; 'the meeting' still typed verbatim). serve_brain.sh 35B THINK=1024 fallback on line 67 is dead code (brain-64 context). Everything else unchanged.

## Tests
18 MLX-only suite failures (main 2528, cool-tasks 2544 passed). Review repros: main 75 / 53, cool-tasks 75 / 53.

# Brain lane review: pass 87 (2026-10-25T10:12Z)

Open: P0 0, P1 16, P2 29. No new findings.

## Branches
- main b92677f: c37f6ee keeps the MLX worker alive when a queued request is cancelled (set_running_or_notify_cancel + done() guards); generic_decide initialises temperature attrs. Verified with stub: worker survives queued and running cancellation. No findings. README outside lane.
- wip/local f1e504c: snapshot on main; lane identical.
- cloud/cool-tasks 3937e6b: unchanged.

## Rechecked
All open findings unchanged; review repro failure set identical to pass 86.

## Tests
main 18 MLX-only suite failures, 2527 passed. Review repros: main 72 / 53.

# Brain lane review: pass 86 (2026-10-25T10:10Z)

Open: P0 0, P1 16, P2 29. New: brain-74 (P2).

## Branches
- main ca73c12: merged native-tools 6053e4e and ui-progress a66166b (identical to pass-83 review); 93ca931 destructive-request refuse gate.
- wip/local 47f809a: snapshot on main; lane identical.
- cloud/cool-tasks 3937e6b: merge of main through 85958b0; brain-72 now on it.

## New
- brain-74 (P2, main): the refuse gate matches delete/remove/format ... all/every and any 'all files'; 'show all files in Downloads', 'delete all completed reminders', 'remove all items from my cart' are refused. Repro test_brain_pass86.py 4/4. Refusals also skip tracer.finish.

## Rechecked
All open findings unchanged; no prior repro changed status.

## Tests
18 MLX-only suite failures on both (main 2527, cool-tasks 2492 passed). Review repros: main 72 / 53, cool-tasks 68 / 57.
