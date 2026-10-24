# bench digest — pass 1

No P0. `cloud/bench` not pushed yet; lane files absent on all branches. Findings are against the spec (`cloud/builder_bench.md@410c9a1`), `decision.py@bcd3b75`, `dedup.py@56ef91b` vs upstream scorers.

## Open P1 (ranked)
1. bench-8 — Dedup crashes on external-utterance schema and silently skips HobbyLM — `training/src/muselet_train/dedup.py`
2. bench-1 — Shim noul answer shape cannot satisfy both DeskMind/JevBench and Typed Decisions — `cloud/builder_bench.md`
3. bench-2 — DeskMind payloads exceed 58-option one-token alphabet; no overflow strategy specified — `ml/src/brain/decision.py`
4. bench-3 — Per-question Decider + options-in-system re-prefills large state per question — `cloud/builder_bench.md`
5. bench-6 — HobbyLM replay graders must reuse HobbyLM per-kind criteria, pre-registered — `cloud/builder_bench.md`
6. bench-4 — DeskMind comparison not pinned to suite, locale, or regradable run format — `cloud/builder_bench.md`
7. bench-5 — Latency compared across incompatible definitions (model-only vs end-to-end) — `cloud/builder_bench.md`
8. bench-7 — HobbyLM event replay can send real calendar invites from lead's account — `cloud/builder_bench.md`

## Highest-leverage next moves
- Fix dedup to read `evals/external/utterances.jsonl` (`text` key) and fail loudly when HobbyLM tests are missing, before the next router training run.
- Shim answer: noul = scalar `noul` + `probabilities{false,true}`; test each saved example against all three vendored upstream scorers.
- generic_decide: state-first KV snapshot + per-question suffix; tournament for >58 options (DeskMind fixtures go to 240).
- Pre-register graders/mappings (HobbyLM kinds, 'none' tasks) and one latency definition pair (model/decision, wall/task) for all systems.
- Pin DeskMind diag-v25 + locale, 3 repeats, grade Muselet with `deskmind-bench score`; isolate calendar for HobbyLM event tasks.
