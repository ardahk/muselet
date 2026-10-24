# architect digest - pass 24 (2026-10-24T10:42Z)
Reviewed: main d514300, wip/local b63699f, cloud/data-pipeline f13aa6d, cloud/decisions c08a96d, cloud/finance 529e9ff, cloud/finance-2 dfaf785, cloud/finance-3 31be399, cloud/fixtures-docs 4bf2291, cloud/bench f584cb2, cloud/advisor 9432c30, cloud/advisor-2 0a65f75, cloud/advisor-3 ca93147, cloud/pitch ad1b058, cloud/pitch-2 3303678, cloud/brain-2 741465c, cloud/brain-3 14a3f52, cloud/brain-4 dfb66a3, cloud/brain-5 b752261, cloud/hobby-gaps 929b931, cloud/grounding 3441ee8.
New: main merged brain-4 and HandsKit batch 5 (media keys, brightness delta, launch read-back, timers RPC, lock-screen guard) and added tools/serve_brain.sh; data-pipeline fixed the tied-head export (f39efe4); brain-5 treats not_frontmost as a terminal failure.

## Open P0/P1 (ranked)
1. architect-17 P1 - serve_brain.sh defaults to a pre-untie-fix, stale-data router that loses e2e (.702 vs .716) - tools/serve_brain.sh
2. architect-12 P1 - Main LoRA trained on stale route data; it2 pending - training/src/muselet_train/datums.py (cloud/data-pipeline)
3. architect-8 P1 - router_check numbers exist but aren't committed; parity unverified - evals/router_check.py
4. architect-10 P1 - Grounder unused at runtime; no builder assigned - ml/src/brain/orchestrator.py:785
5. architect-13 P1 - Cloud Tinker System One backend reports as 'muselet' - bench/systemone/cli.py:42 (cloud/decisions)
(P2: architect-15 delta/view not in catalog; architect-16 timers RPCs have no skill)

## Highest-leverage next moves
1. Re-export main-final with `export untie`, run parity, rerun router_check route + ARGS e2e for the 2x2 {trained,base} grid; default to the e2e winner (currently base). ~45 min.
2. Finish it2 on the pinned val with the fixed export, gated on ARGS EM runtime. ~1.5 h.
3. Merge hobby-gaps, then rebase brain-5 onto catalog delta/view (3 conflicts now). ~30 min.
4. Assign Grounder click wiring. ~1 h.
5. Add cancel_timer/list_timers catalog skills over the new timers RPCs. ~30 min.
