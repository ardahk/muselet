# architect digest — pass 3 (2026-10-24T05:45Z)
Reviewed: main 10793e0, wip/local 1d7cc07, cloud/data-pipeline 4cbb74a, cloud/finance f098120, cloud/fixtures-docs 4bf2291.
Resolved this pass: architect-4 (utterance ctx implemented on both sides). decision.py compiles again; test_route_parity.py added.

## Open P0/P1 (ranked)
1. architect-1 P0 — No System 2 planner: every multi-step demo flow ends "coming soon" — ml/src/brain/orchestrator.py
2. architect-3 P0 — premiere_command / start_timer route fine, then throw notImplemented — app/Sources/HandsKit/Skills.swift
3. architect-6 P1 — Executor drops expects, ends batches at scripts; click coords 0-1000 vs points (done-batch part fixed in prompt) — orchestrator.py / planner_system.md
4. architect-8 P1 — Phase-1 LoRA likely misses Sat 12:00 PDT; no measured fallback router — training/SPEC.md
5. architect-9 P1 — Finance engine reachable only via CLI, not from voice/brain — cloud/finance ml/src/brain/finance
6. architect-5 P1 — Partials dropped; ARGS decode always serial after release — server.py
7. architect-7 P1 — No benchmark harness (HobbyLM 125, DeskMind 13, JevBench, /v1/systemone) — bench/

## Highest-leverage next moves
1. Planner loop (architect-1) with streaming DSL execution on the cached 4B/9B. Unblocks the browser, Numbers and Premiere flows and DeskMind Bench. ~4-6 h.
2. premiere_command as Swift keystrokes, plus executor fixes: scripts continue the batch, expect is forwarded on script/skill, click coords converted (architect-3, -6). ~2 h.
3. Wire the finance engine in as brain-side skills (finance_analyze -> generated Numbers scripts executed with expects) and point planner rule 8 at it (architect-9). This makes the Numbers demo deterministic. ~2 h.
4. Speculative route+args on partials; skip args for zero-arg skills (architect-5). Route+args comes off the critical path for instant commands. ~2 h.
5. /v1/systemone shim + HobbyLM 125-task adapter (architect-7), and a lead call on trimming Phase-1 data (architect-8). ~5 h + a decision.
