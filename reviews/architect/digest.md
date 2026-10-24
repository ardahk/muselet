# architect digest — pass 1 (2026-10-24T05:20Z)
Reviewed: main cdae5d9, wip/local b438799, cloud/data-pipeline 5da307e, cloud/fixtures-docs 4bf2291.

## Open P0/P1 (ranked)
1. architect-1 P0 — No System 2 planner: every multi-step demo flow ends "coming soon" — ml/src/brain/orchestrator.py
2. architect-2 P0 — Runtime router prompt differs from training render (LoRA mismatch) — ml/src/brain/decision.py
3. architect-3 P0 — premiere_command / start_timer route fine, then throw notImplemented — app/Sources/HandsKit/Skills.swift
4. architect-6 P1 — Executor drops expects, ends batches at scripts; click coords 0-1000 vs points — orchestrator.py / planner_system.md
5. architect-8 P1 — Phase-1 LoRA likely misses Sat 12:00 PDT; no measured fallback router — training/SPEC.md
6. architect-4 P1 — Router context always app=none; online check stale and blocking — orchestrator.py / decision.py
7. architect-5 P1 — Partials dropped; ARGS decode always serial after release — server.py
8. architect-7 P1 — No benchmark harness (HobbyLM 125, DeskMind 13, JevBench, /v1/systemone) — bench/

## Highest-leverage next moves
1. Planner loop (architect-1) with streaming DSL execution on the already-cached 4B/9B: unlocks browser, Numbers, Premiere and DeskMind Bench. Payoff: 3 of 4 demo flows go from 0 to possible. Effort ~4-6 h.
2. Make runtime render == training render (architect-2) + parity test against cloud's samples file: otherwise the $40 LoRA is served out of distribution. Effort ~1 h.
3. premiere_command as Swift keystrokes + fix script/expect/done in the executor (architect-3, -6): Premiere instant commands and the Numbers script path work and are verified. Effort ~2 h.
4. Speculative route+args on partials, skip args for zero-arg skills, frontmost app in the utterance frame (architect-5, -4): instant command at roughly STT + skill time; context-trained behaviours fire. Effort ~2-3 h.
5. /v1/systemone shim + HobbyLM 125-task adapter (architect-7), and a lead call on trimming Phase-1 data so training starts by ~08:00 PDT (architect-8). Effort ~5 h + a decision.
