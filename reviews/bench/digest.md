# bench digest — pass 13 (PULSE, 2026-10-24T08:40Z)

P0: 0. Open P1: 2. Open P2: 3. New: bench-16.
Reviewed: cloud/bench@2c57d7f (document-safety guard; 118 tests pass). Other branches unchanged since pass 12.

## Open P0/P1 (ranked)
1. bench-14: Nothing dedups training data against ScreenSpot-Pro/OSWorld-G before grounding training. Becomes P0 once Phase-4 data is built. (training/src/muselet_train/decontam.py)
2. bench-16: Per-run safety skips (open user documents, calendar preflight) give Muselet and HobbyLM different task denominators. (bench/hobbylm/replay.py)

Open P2: bench-11 (systemone CLI defaults to fake with name muselet), bench-12 (chunked probabilities can contradict the stage-2 winner), bench-15 (--limit takes a single-app ScreenSpot-Pro subset).

## Highest-leverage next moves
- Score HobbyLM vs Muselet only on (id, repeat) pairs eligible in both runs, and list the skipped ids (bench-16).
- Before any grounding data build, export the SSPro/OSW-G instructions and image phashes, and make decontam fail closed (bench-14).
- Use a stratified --limit in run_screenspot.py for tuned-vs-tuned grounder runs (bench-15).
- Use the stage-2 argmax for chunked choice answers (bench-12).
- Make --backend mlx the default, or label fake runs 'fake' (bench-11).
