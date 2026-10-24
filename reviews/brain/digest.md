# Brain lane digest, pass 42 (2026-10-24T21:25Z)

Heads moved: main 3876f3a, wip/local 3cfa06d, cloud/comms-2 c65ee70. Others unchanged since pass 41.

Counts (open): P0 0 / P1 9 / P2 10.

Tests (serial): main 1347 passed; bench 165 passed; comms-2 1462 passed; wip/local 1470 passed.
Review repros: 30 failed on main (unchanged); test_brain_pass41.py 5 failed on comms-2@c65ee70 and wip/local.

## Changes this pass
- main 3876f3a: Swift only (messages_people RPC, fuzzy contacts_search, compose v2 with name, windows probe) plus
  bench document-safety/hobbylm changes. Outside the Python lane; messages_people + fuzzy are what comms-2 calls, so
  comms-2 no longer depends on unmerged Swift. No brain code changed, every open finding stands.
- comms-2 c65ee70: does not fix brain-38. 'note' moves into the '<verb> X a note' form: 'send me a note' -> to 'me',
  'send finder a note' -> to 'finder'. brain-38 refreshed.
- wip/local: comms-2 plus newer local comms.py ('saying ... to X', 'tell X to Y' split). Same brain-38 repros fail.

## Top open
1. brain-35 P1 permission gate uses the pre-batch observation (main).
2. brain-38 P1 message parser hijacks non-messaging commands (comms-2, wip/local).
3. brain-25 P1 calculator keys can land in the frontmost app.

Other open P1: brain-29, brain-30, brain-24, brain-16, brain-22, brain-17.
Other open P2: brain-36, brain-37, brain-34, brain-27, brain-28, brain-8, brain-12, brain-14, brain-18, brain-19.
