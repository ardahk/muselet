# evals-safety digest, pass 3 (2026-10-24T05:40:05Z)

## Open P0/P1 (ranked)
1. evals-safety-2 P0: script confirm regex misses rm -rf, doShellScript, Terminal do script (ml/src/brain/orchestrator.py)
2. evals-safety-11 P1: done is trusted, not verified; rule 13 exists only in prompt (ml/src/brain/orchestrator.py)
3. evals-safety-5 P1: confirmed=true arg skips confirm; confirm text omits recipient/body (ml/src/brain/catalog.py, orchestrator.py)
4. evals-safety-6 P1: brain-side confirm for Send/Delete presses still missing (ml/src/brain/orchestrator.py)
5. evals-safety-10 P1: HobbyLM decontam path is checked silently; decontam not wired into the pipeline (training/src/muselet_train/decontam.py)
6. evals-safety-4 P1: 'no' string is truthy, so #20 still renders online=yes; no tau gating metric (ml/src/brain/decision.py)

Resolved this pass: -1 (eval leak), -3 (args coercion), -9 (SyntaxError), -7 (finance realism).
Checked and clean: cloud/finance fixtures recomputed independently (totals, categories, dups [[18,19],[66,67]], outlier [85], refund [105], budget, receipts 1-8 all match; regeneration byte-identical). The finance engine reproduces every key; its BERKELEY BOWL ask is intended and tested. Its 90 tests pass on Linux. numbers_script escapes every string with q().

## Highest-leverage next moves
- Replace the script blocklist with an allowlist and strip `confirmed` from model args. These are the last unconfirmed-destructive paths.
- Enforce verified `done` in the executor before any success-rate number is published.
- Make `python -m muselet_train.decontam` a required step in the pipeline, and assert the HobbyLM path exists and the eval counts are > 0.
- Add a weekend key to the finance truth, and parse 'yes'/'no' ctx strings in RouteRenderer.
