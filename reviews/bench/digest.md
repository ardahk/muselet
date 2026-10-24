# bench digest — pass 9 (PULSE, 2026-10-24T08:00Z)

P0: 0. Open P1: 1. Open P2: 3. Resolved this pass: bench-4 (diag-v27 + Hands pin enforced), bench-5 (parent-clocked HobbyLM worker), bench-7 (local-calendar preflight + invite guards).
Reviewed: main@4a74659, wip/local@85c73ed, cloud/bench@c3ca0b3, cloud/data-pipeline@9c526b1, cloud/grounding@3441ee8 (merged to main).

## Open P0/P1
1. bench-14: Nothing dedups training data against ScreenSpot-Pro/OSWorld-G before grounding training. Becomes P0 once Phase-4 data is built. (training/src/muselet_train/decontam.py)

Open P2: bench-11 (systemone CLI defaults to --backend fake with --model-name muselet), bench-12 (chunked probabilities can contradict the stage-2 winner), bench-15 (--limit takes a single-app ScreenSpot-Pro subset).

## Highest-leverage next moves
- Before any grounding data build, export the SSPro/OSW-G instructions and image phashes, and make decontam fail closed (bench-14).
- Make --backend mlx the default, or label fake runs 'fake' in served model names and results (bench-11).
- Use the stage-2 argmax for chunked choice answers (bench-12) before DeskMind runs with >58 options.
- Use a stratified --limit in run_screenspot.py before quick model selection (bench-15).
