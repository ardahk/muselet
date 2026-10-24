# Brain lane digest, pass 41 (2026-10-24T21:10Z)

Heads: main 27ebd13, wip/local 4585ce4, cloud/comms-2 265c86d, cloud/planner-retrieval 9786fa4,
cloud/clock-timers d060b5a, cloud/mascot-animal 238db23, cloud/data-pipeline 34aff30, cloud/decisions b78d778.

Counts (open): P0 0 / P1 9 / P2 10.

Tests (serial; a parallel run showed spurious failures from shared state):
main 1347 passed; comms-2 1462 passed; planner-retrieval 1366 passed; clock-timers 1362 passed.
Review repros: 30 failed on main and on every new branch (brain-35/36 included).

## Changes this pass
- New brain-38 (P1, comms-2): comms.parse_message runs before the router and hijacks 'tell finder ...', 'tell spotify ...',
  'text size bigger'; 'send a message to John on Slack' composes 'on Slack' into John's Messages conversation.
- brain-22: planner-retrieval's retrieved examples use the marked history form next to DSL live history.
- brain-37: retrieval block is another prompt shape the planner demos don't cover.
- main 27ebd13: create_event datetimes now carry the local offset (catalog.py); no finding.
- clock-timers: delayed one-time Clock hint; no finding. mascot-animal, decisions, data-pipeline: outside lane.

## Top open
1. brain-35 P1 permission gate uses the pre-batch observation (main).
2. brain-38 P1 message parser hijacks non-messaging commands (comms-2).
3. brain-25 P1 calculator keys can land in the frontmost app.

Other open P1: brain-29, brain-30, brain-24, brain-16, brain-22, brain-17.
Other open P2: brain-36, brain-37, brain-34, brain-27, brain-28, brain-8, brain-12, brain-14, brain-18, brain-19.
