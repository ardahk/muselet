# Brain lane review: pass 85 (2026-10-25T09:50Z)

Open: P0 0, P1 16, P2 28. New: brain-73 (P1), brain-72 (P2).

## Branches
- main 85958b0: a524768 soft expects for any task with a finish criterion; 71badc3 shopping guard on create_reminder. Shopping few-shot outside the lane.
- wip/local 3d21638: snapshot on main; lane identical.
- cloud/cool-tasks a77104e: merge of main through a524768.

## New
- brain-73 (P1, main + cool-tasks): a failed expect returns ok, so the rest of the batch runs. Repro test_brain_pass85.py: typing after a failed expect runs on 85958b0, stops on 2445a1d.
- brain-72 (P2, main): 'remind me to buy milk' / 'shop for' / 'Target' reminders rerouted to the planner. Repro 3/3.

## Rechecked
All open findings unchanged; no prior repro changed status.

## Tests
18 MLX-only suite failures on both (main 2476, cool-tasks 2492 passed). Review repros: main 68 / 53, cool-tasks 65 / 56.
