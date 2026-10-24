# evals-safety digest — pass 47 (main@3772f7c, wip/local@8fcf55f)

Open: P0 1, P1 10, P2 9.

## Open P0/P1 (ranked)
1. **-37 (P0):** script policy lets System Events shut down / restart / log out and Finder empty / eject run with no confirm. A read verb anywhere, even in a comment, exempts the script. (`ml/src/brain/orchestrator.py`). Fix is on cloud/w9-safety 50a3b25; merge it.
2. **-41 (P1):** the brain WS on :8765 has no Origin or token check, so any web page can send utterances and confirm_reply yes. (`ml/src/brain/server.py`)
3. **-38 (P1):** `tell app "X"` is not parsed; one Numbers tell block masks other targets. (`orchestrator.py`)
4. **-39 (P1):** the finance rules miss BERKELEY BOWL. Groceries comes out 203.61 vs the key's 298.70 without the model. (`ml/src/brain/finance/categorize.py`)
5. **-36 (P1):** the v2 clobbering accept rules are now retrievable, because main ships RETRIEVAL_K=1.
6. **-42 (P1):** route_v1 case 87 is mislabeled (it should be draft_email); cases 73 and 89 are ambiguous. All three are in the clean set.
7. **-40 (P1):** the finance fixtures contradict `cloud/session_b.md` (rent 1625, Netflix 7.99, PEET'S, ranges, receipt 05 date). The keys themselves recompute correctly.
8. **-43 (P1):** the Tinker trainers check only their per-run estimate, not month-to-date spend against the $148 stop.
9. **-25 (P1):** skipped and manual live cases are excluded from the denominator.
10. **-11 (P1):** `done` has no harness goal check.

## Next moves
1. Patch `_SCRIPT_BLOCK`/targets (-37/-38) and set `origins=[None]` on the WS server (-41). These are small diffs that close the destructive and remote paths.
2. Add BERKELEY BOWL to the Groceries rules, plus a no-model fixture==truth test (-39).
3. Relabel route_v1 case 87 and re-quote it2 on clean (-42).
4. Pick one finance contract (amend session_b.md or regenerate) (-40).
5. Gate every Tinker launch on month-to-date + lag ledger + estimate <= $148 (-43).
