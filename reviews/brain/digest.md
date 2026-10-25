# Brain lane digest — pass 72 (2026-10-25T05:55Z)

Open: **P0 0 / P1 10 / P2 16**. New: brain-54 (cloud/agentic-loop). brain-53 moved onto main.

## Branches
- **main e8023b8**: merged #87 (blind planner, as reviewed on wip 323d274 in pass 71, plus the test_grounder_wire import fix) and #88 (blind typing; no lane files).
- **wip/local 20055d1**: snapshot on main@8b15e29; lane identical to main.
- **cloud/agentic-loop 9b2e512** (new):
  - Done is accepted on rule-based finish evidence before any expect/model check -> brain-54.
  - A failed expect re-polls verify for up to 5 s while the page is loading; one loading failure skips a loop-guard strike. Looks right.
  - Learned workflows are only saved after non-app done evidence and with >=2 real actions; loaded into retrieval once. Looks right.
  - Retrieval skips demos for a different app/site. Looks right.

## New
- **brain-54 (P1, agentic-loop)**: finish.evidence counts "not playing" stdout as playing, Google Maps' Directions button as a route, and "flights" in the title as done for "search for flights to tokyo and book the cheapest one". Accepted without the verifier. Repro tests/test_brain_pass72.py: 3/3 fail on agentic-loop.

## Rechecks
- **brain-53 (P2, now main)**: test_brain_pass71.py fails 5/5 on main.
- All other open findings unchanged on main.

## Tests (MLX stub, Linux)
- main, wip/local: 18 failed (MLX-only) / 2334 passed. agentic-loop: 18 failed (MLX-only) / 2351 passed.
- Review repros: main/wip 40 failed / 54 passed; agentic-loop 43 failed.
