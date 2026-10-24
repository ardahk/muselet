# evals-safety digest, pass 4 (2026-10-24T05:57:14Z)

## Open P0/P1 (ranked)
1. evals-safety-2 P0: script allowlist still lets System Events click, Safari do JavaScript/open location, and raw «event» run unconfirmed (ml/src/brain/orchestrator.py)
2. evals-safety-14 P1: bool 'on' regex override inverts mute and 'off and back on' (ml/src/brain/orchestrator.py)
3. evals-safety-15 P1: evals/external uses 'text' key, so decontam/dedup crash with KeyError (training/src/muselet_train/decontam.py)
4. evals-safety-16 P1: HobbyLM frozen task files gitignored, baseline not reproducible (.gitignore, bench/hobbylm/)
5. evals-safety-11 P1: done is still not final-state verified (ml/src/brain/orchestrator.py)
6. evals-safety-6 P1: `type ... enter` in Messages/Slack composers and System Events clicks skip confirm (ml/src/brain/orchestrator.py)
7. evals-safety-10 P1: HobbyLM decontam path read without checking it exists; decontam not in the pipeline (training/src/muselet_train/decontam.py)
8. evals-safety-4 P1: 'no' string is truthy, so case #20 renders online=yes (ml/src/brain/decision.py)

Resolved this pass: -5 (self-confirm and confirm text).
Checked and clean: advisor Henderson truth recomputed independently (totals, allocation, rebalance, TLH and wash sale, cash, Roth, donation all match; regeneration byte-identical 8/8). finance@529e9ff TAX REFUND change is fine. Finance and advisor tests pass (113 on wip), bench tests pass (8 + 1 skip). JevBench/typed_decisions score invalid answers as wrong and record --limit. No secret-like strings in new commits.

## Highest-leverage next moves
- Remove System Events from the script read allowlist and block `click|do JavaScript|open location|«event`.
- Limit the `on` override to wifi/bluetooth/dark_mode, or drop it; mute is inverted today.
- Un-ignore bench/hobbylm/upstream/data and read `text` or `utterance` in decontam/dedup before merging cloud/bench.
- Freeze route_v1 at 128 cases and put the catalog-v2 cases in route_v2.
