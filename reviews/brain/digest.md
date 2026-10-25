# Brain lane review: pass 84 (2026-10-25T09:35Z)

Open: P0 0, P1 15, P2 27. No new findings.

## Branches
- main 2445a1d: sendgate exempts 'Ask Gmail'; new email_open finish criterion/evidence. Shopping/maps hints outside the lane.
- wip/local 6e7f50b: snapshot on main; lane identical.
- cloud/cool-tasks e4def97: merge of main only; brain-69 now on it.

## Rechecked
- brain-69 still open (and wider by one phrase); repro fails 2/2 on main and cool-tasks.
- brain-70, brain-71 unchanged on cool-tasks. All other open findings unchanged.
- Observation: email_open evidence does not check the message is opened or latest; relational senders ('my boss') never match.

## Tests
18 MLX-only suite failures on both branches (main 2476, cool-tasks 2492 passed). Review repros: 64 failed / 53 passed on both.
