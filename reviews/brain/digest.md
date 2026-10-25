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
