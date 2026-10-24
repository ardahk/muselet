# bench digest — pass 15 (PULSE, 2026-10-24T09:08Z)

P0: 0. Open P1: 3. Open P2: 3. New: bench-17 (pass 14), bench-16 (pass 13).
Reviewed: cloud/bench@f584cb2 (127 tests pass), cloud/data-pipeline@70b7d1b (bench-17 still open), main@bb494af, wip/local@c85a000.

## Open P0/P1 (ranked)
1. bench-14: Nothing dedups training data against ScreenSpot-Pro/OSWorld-G before grounding training. Becomes P0 once Phase-4 data is built. (training/src/muselet_train/decontam.py)
2. bench-17: The Phase 1 trainer now reads route_train/route_val, which no committed code writes, so there is no proof the data passed eval decontam. (training/src/muselet_train/datums.py)
3. bench-16: Per-run safety skips (open user documents, calendar preflight) give Muselet and HobbyLM different task denominators. (bench/hobbylm/replay.py)

Open P2: bench-11 (systemone CLI defaults to fake with name muselet), bench-12 (chunked probabilities can contradict the stage-2 winner), bench-15 (--limit takes a single-app ScreenSpot-Pro subset).

## Highest-leverage next moves
- Commit the route_train/route_val split script, and make datums refuse a split without an eval-decontam sidecar (bench-17).
- Score HobbyLM vs Muselet only on (id, repeat) pairs eligible in both runs, and list the skipped ids (bench-16).
- Before any grounding data build, export the SSPro/OSW-G instructions and image phashes, and make decontam fail closed (bench-14).
- Use a stratified --limit in run_screenspot.py for tuned-vs-tuned grounder runs (bench-15).
- Use the stage-2 argmax for chunked choice answers (bench-12).
