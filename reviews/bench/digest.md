# bench digest — pass 3

No P0. bench-1 and bench-3 were fixed on cloud/bench@8429245.

## Open P1 (ranked)
1. bench-8 — Dedup crashes on external-utterance schema and silently skips HobbyLM — `training/src/muselet_train/decontam.py` (reproduced KeyError once cloud/bench merges)
2. bench-9 — Muselet event grade never checks the created event's date/time/invitee — `bench/hobbylm/replay.py`
3. bench-6 — HobbyLM replay graders must reuse HobbyLM per-kind criteria, pre-registered (Muselet pass is looser) — `bench/hobbylm/replay.py`
4. bench-10 — Timer tasks auto-fail for Muselet but grade normally for HobbyLM — `bench/hobbylm/replay.py`
5. bench-2 — DeskMind payloads exceed 58-option one-token alphabet; no overflow strategy specified (whole request 400s) — `ml/src/brain/generic_decide.py`
6. bench-5 — Latency compared across incompatible definitions — `bench/hobbylm/replay.py`
7. bench-7 — HobbyLM event replay can send real calendar invites from lead's account — `bench/hobbylm/replay.py`
8. bench-4 — DeskMind comparison not pinned to suite, locale, or regradable run format (Hands pin mismatch) — `bench/deskmind/README.md`

## Highest-leverage next moves
- Fix decontam/dedup to read `text` from evals/external/utterances.jsonl before cloud/bench merges; otherwise the next training run crashes or someone skips the file.
- replay.py: one grader table for both systems (final-state + reported-success); event readback compares the created event, not the request; timers graded from the trace.
- generic_decide: chunked tournament for >58 options so DeskMind requests with large heads stop returning 400.
- Pin Hands 3d54492 for diag-v25; record the backend and model path in every runner's command.txt.
- Use one external clock and the same polling probe for both systems in HobbyLM replay.
