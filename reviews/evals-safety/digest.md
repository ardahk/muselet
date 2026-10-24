# evals-safety digest, pass 2 (2026-10-24T05:24:11Z)

## Open P0/P1 (ranked)
1. evals-safety-2 P0: script confirm regex misses rm -rf, doShellScript, Terminal do script (ml/src/brain/orchestrator.py)
2. evals-safety-1 P0 (mostly fixed by ea64ce3): 2 eval items still used as generator few-shots, 5 near-dups (training/src/muselet_train/prompts.py)
3. evals-safety-9 P1: decision.py SyntaxError, brain cannot import at wip bcd3b75 (ml/src/brain/decision.py)
4. evals-safety-10 P1: eval dedup uses stale route_v1 and silently skips HobbyLM tests (training/src/muselet_train/dedup.py)
5. evals-safety-11 P1: done is trusted, not verified; rule 13 exists only in prompt (ml/src/brain/orchestrator.py)
6. evals-safety-5 P1: confirmed=true arg skips confirm; confirm text omits recipient/body (ml/src/brain/catalog.py, orchestrator.py)
7. evals-safety-3 P1: eval-route args_exact compares raw strings to typed labels (ml/src/brain/cli.py)
8. evals-safety-4 P1: 'no' string is truthy, so #20 still renders online=yes; no tau gating (ml/src/brain/decision.py)
9. evals-safety-6 P1: brain-side confirm for Send/Delete presses still missing (planner rule 12 landed) (ml/src/brain/orchestrator.py)

## Highest-leverage next moves
- Fix decision.py (evals-safety-9) first: nothing in the brain runs at this snapshot.
- Rebase cloud/data-pipeline onto main (or read evals from origin/main) before the full dedup, and assert the HobbyLM path exists.
- Replace the script blocklist with an allowlist; strip `confirmed` from model args.
- Enforce verified done in the executor and score evals on verified final state only.
- Make eval-route use the production arg coercion and bool parsing for ctx strings ('no' -> False).
