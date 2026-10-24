# bench digest — pass 8 (PULSE, 2026-10-24T07:55Z)

P0: 0. Open P1: 4. Open P2: 3. Resolved this pass: bench-8 (decontam text key, b8c0604), bench-13 (native-scale runtime zoom, 3441ee8).
Reviewed: main@d8ad966, wip/local@85ec0df, cloud/bench@911a384, cloud/data-pipeline@b8c0604, cloud/grounding@3441ee8, cloud/brain-2@741465c, cloud/finance-2@dfaf785, cloud/advisor-2@0a65f75, cloud/pitch@ad1b058.

## Open P0/P1 (ranked)
1. bench-14: Nothing dedups training data against ScreenSpot-Pro/OSWorld-G before grounding training. Becomes P0 once Phase-4 data is built. (training/src/muselet_train/decontam.py)
2. bench-7: Event replay can send real invites, because the calendar isn't proven to be local. (bench/hobbylm/replay.py)
3. bench-5: The latency clocks differ. Muselet's stops at its verified check; HobbyLM's is its self-reported seconds_total. (bench/hobbylm/replay.py)
4. bench-4: DeskMind's Hands pin, locale and suite version don't match diag-v25. (bench/deskmind/README.md)

Open P2: bench-11 (fake backend labeled muselet), bench-12 (chunked probabilities can contradict the stage-2 winner), bench-15 (--limit takes a single-app subset).

## Highest-leverage next moves
- Before any grounding data build, export the SSPro/OSW-G instructions and image phashes to evals/external, and make decontam fail closed (bench-14).
- Require a local "On My Mac" calendar for event replay, or strip invitees (bench-7).
- Time HobbyLM with the same harness/core poller Muselet uses (bench-5).
- Pin Hands to 3d54492 for diag-v25 and record the locale in results (bench-4).
- Use a stratified --limit in run_screenspot.py before any quick model-selection run (bench-15).
