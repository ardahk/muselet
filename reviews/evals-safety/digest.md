# evals-safety digest, pass 19 (2026-10-24T09:33:44Z): main 28dc259

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-29 P1 (cloud/hobby-gaps): calc.result runs before the router; 'text Alex that 2 of the 5 tickets are left' -> '5-2 is 3', not sent (ml/src/brain/orchestrator.py:296, calc.py:258)
2. evals-safety-25 P1: the document guard skips 9/43 live cases and drops them from the denominator (bench/harness/documents.py, bench/live/run_live.py)
3. evals-safety-6 P1: Enter/Send in Discord/WhatsApp/web composers is unconfirmed (ml/src/brain/orchestrator.py)
4. evals-safety-11 P1: done is accepted after an expect-less batch + fresh observe (ml/src/brain/orchestrator.py)
5. evals-safety-23 P1: the spend guard's level-only latch and $10 margin (tools/review_pulse.sh:25-31)
6. evals-safety-26 P1 (cloud/data-pipeline): main-final's training rows have no decontam record (training/src/muselet_train/datums_export.py)

Resolved this pass: -27 (it2 selection is val-only, 2319e72). Open P2: -8, -12 (now also router_check e2e), -20, -21, -22, -24, -28.
Checked, nothing material: planner_offline holdout set (opt-in --set holdout, written after the sweep); brain-4 planner flags (done_alone/constraint only shape decoding; the harness done gate is unchanged); data-pipeline ARGS runtime EM.

## Highest-leverage next moves
- Before merging hobby-gaps, gate calc behind the ANSWER label or Calculator context (-29).
- Scope the doc guard to the case's own apps, and print skipped alongside passed/executed (-25).
- Confirm `type ... enter` in any chat-like composer (-6). Require a passed expect before done (-11).
- Export main's rows with --reader dedup and decontam them (-26).
- Fix the guard latch, and cap tokens in the Tinker bench backend (-23, -28).
