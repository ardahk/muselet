# bench digest — pass 4

No P0. Fixed on cloud/bench@14c7eb1: bench-1, -2, -3, -6, -9, -10 (the timer gap is now disclosed in coverage.md).

## Open P1 (ranked)
1. bench-8 — Dedup crashes on external-utterance schema and silently skips HobbyLM — `training/src/muselet_train/decontam.py`
2. bench-5 — Latency compared across incompatible definitions — `bench/hobbylm/replay.py`
3. bench-7 — HobbyLM event replay can send real calendar invites from lead's account — `bench/hobbylm/replay.py`
4. bench-4 — DeskMind Hands pin 3c1ceac vs diag-v25's 3d54492 — `bench/deskmind/README.md`

Open P2: bench-11 (fake-backend runs labelled muselet), bench-12 (chunked combine contradicts stage-two winner).

## cloud/grounding
Branch not pushed yet. Will review CANDIDATES.md citations, per-adapter coordinate conventions, zoom-crop mapping, grounder.py, and whether ScreenSpot-Pro data could reach training (cache path, training globs).

## Highest-leverage next moves
- decontam/dedup: read `text`/`source` rows from evals/external before cloud/bench merges to main.
- replay latency: same kinds, same probe, same clock for both systems.
- Event trials: require a local ('On My Mac') Hobby Test calendar, or strip attendees in bench mode.
- Pin Hands 3d54492 for diag-v25; record the backend and model in runner command.txt.
- combine_chunked: answer = stage-two argmax.
