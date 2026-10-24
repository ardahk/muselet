# architect digest - pass 16 (2026-10-24T08:55Z)
Reviewed: main 280715d, wip/local 38768f3, cloud/data-pipeline a6b229a, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench 2c57d7f, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/grounding 3441ee8.
cloud/data-pipeline: Phase-1 main run done (Qwen3.5-4B LoRA, 496 steps, $29.45). Full val: top1 0.918, macro-F1 0.885, ECE 0.016, ARGS EM 0.869.

## Open P0/P1 (ranked)
1. architect-12 P1 - Main run likely trained on stale route_dedup.jsonl (fix landed 2 min after the report) - training/src/muselet_train/datums.py:57
2. architect-8 P1 - Phase-1: MLX parity and base-model score still missing; about 3 h to Sat 12:00 PDT - training/
3. architect-11 P1 - Brain ignores web_ax_pending/no_text_target/exit_code from HandsKit - ml/src/brain/orchestrator.py
4. architect-10 P1 - Grounder merged but unused; every pixel click fails - ml/src/brain/orchestrator.py:593

## Highest-leverage next moves
1. Check whether data/v2all/route_dedup.jsonl differs from route_train/route_val; if it does, rerun main with a6b229a (about $30, about 1 h) before exporting. ~10 min to check.
2. Export the adapter, run sharded mlx_parity on the Mac against parity_300, and score the base 4B/0.8B on route_val with eval_route (tuned vs tuned). ~1 h.
3. Merge cloud/brain-3 (architect-11). ~30 min.
4. Wire the Grounder into the click path (architect-10). ~1 h.
5. Run the four demo flows through live_t1, then HobbyLM-125 and DeskMind-13 on cloud/bench. ~4 h.
