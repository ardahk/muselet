# bench digest — pass 6 (self-poll, 2026-10-24T07:30Z)

P0: 0. Open P1: 6. Open P2: 3. Reviewed: cloud/bench@911a384, cloud/grounding@42310cd, cloud/data-pipeline@8f0b9bc, main@c2d2988, wip/local@d5d2d7d, cloud/brain-2@9f41c11.

## Open P0/P1 (ranked)
1. bench-8 — decontam/dedup crash on evals/external `text` rows; HobbyLM path hard-coded. The Phase 1 trainer now consumes route_dedup.jsonl, and the reports give no decontam count — training/src/muselet_train/{decontam,dedup,datums}.py
2. bench-14 — No dedup for ScreenSpot-Pro/OSWorld-G before grounding training (becomes P0 when Phase-4 data is built) — training/src/muselet_train/decontam.py
3. bench-13 — Runtime zoom re-crops the 1 MP shot, so the bench's zoom gain won't transfer — ml/src/brain/grounder.py
4. bench-7 — Event replay can send real invites (calendar not proven local) — bench/hobbylm/replay.py
5. bench-5 — Latency clocks still differ: verified-check vs self-reported seconds_total — bench/hobbylm/replay.py
6. bench-4 — DeskMind Hands pin / locale / suite version vs diag-v25 — bench/deskmind/README.md

Open P2: bench-11 (fake backend labeled muselet), bench-12 (chunked probs contradict stage-2 winner), bench-15 (--limit takes a single-app subset).

Checked on grounding, no defect found: to_global matches HandsKit `global = origin + px/scale` (negative origins OK). norm1000/unit/resized_px conversions and crop offsets are correct. OSWorld-G bbox is [x,y,w,h] (confirmed against HF row + mimo_bbox) and has 510 rows. Every candidate score has a source and caveats (unverified conventions flagged). 114 grounder tests pass. bench tests: 30 pass, 1 env-only fail.

## Highest-leverage next moves
- Fix decontam to read `text` and fail closed on a missing HobbyLM dir (bench-8). Before any grounding data build, export SSPro/OSW-G instructions + image hashes (bench-14).
- Use zoom only when the source exceeds 1 MP. Wire zoom_region two-shot capture, and run SSPro with `--source-max-pixels 1e6` so zoom numbers reflect runtime (bench-13).
- Require a local "On My Mac" calendar for event replay, or strip invitees (bench-7).
- Time HobbyLM with the same harness poller as Muselet (bench-5).
- Pin Hands to 3d54492 for diag-v25 and record the locale in results (bench-4).
