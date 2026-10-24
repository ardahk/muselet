# evals-safety digest, pass 18 (2026-10-24T09:16:57Z): wip/local 3e03686 has no diff vs main 2920225; open findings unchanged from the pass-17 re-verify

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-25 P1 (now on main): the document guard skips 9/43 live cases on a normal Mac and drops them from the denominator (bench/harness/documents.py, bench/live/run_live.py)
2. evals-safety-6 P1: Enter/Send in Discord/WhatsApp/web composers is unconfirmed. The "Message #general" / "Type a message" labels miss the regex (ml/src/brain/orchestrator.py:589-806)
3. evals-safety-11 P1: done is accepted after an expect-less batch + fresh observe, with no final-state check (ml/src/brain/orchestrator.py:1076-1093)
4. evals-safety-23 P1: the spend guard's level-only latch and $10 margin are unchanged (tools/review_pulse.sh:25-31)
5. evals-safety-26 P1 (cloud/data-pipeline, PR #2): main-final's training rows have no decontam record. datums_export --reader dedup can now export them (training/src/muselet_train/datums_export.py)
6. evals-safety-27 P1 (cloud/data-pipeline): it2 go/no-go is gated on route_v1 (training/reports/phase1_it2_plan.md)

Open P2: -8, -12, -20, -21, -22, -24 (now 12/43 without a state check), -28 (new, cloud/decisions Tinker backend uncapped). Resolved this pass: -17.
Checked on main, nothing material: planner_offline primary grading uses dsl.action_line like orchestrator.py:1004 and keeps the safety rejects. Compiled skill scripts pass args as handler params (AppleScript.swift:103-104). 455 ml tests + 118 bench tests pass (mlx/PIL/pyarrow-only files can't run on Linux).

## Highest-leverage next moves
- Scope the doc guard to the case's own apps, and print skipped alongside passed/executed (-25).
- Confirm `type ... enter` in any chat-like composer: match "message" labels or use an app list incl. Discord/WhatsApp/Teams/web (-6).
- Require a passed expect (not just fresh observe) before done (-11).
- Export main's rows with --reader dedup and decontam them. Gate it2 on val only (-26, -27).
- Fix the guard latch, and add a token cap to the Tinker bench backend before any Tinker bench run (-23, -28).
