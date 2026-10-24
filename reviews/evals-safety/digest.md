# evals-safety digest, pass 15 (2026-10-24T08:47:24Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-26 P1: the Phase-1 main checkpoint (est $29.45) was trained from route_dedup.jsonl, which no committed dedup writes. Its decontam state is unrecorded, and the fix came 2 min after the report (training/src/muselet_train/datums.py)
2. evals-safety-23 P1: spend guard at $120/$140. The level-only latch can skip the $120 warning, and the $140 stop leaves $10 against hours of billing lag (tools/review_pulse.sh, tools/tinker_spend.py)
3. evals-safety-25 P1: the cloud/bench document guard inventories all 24 apps for 9 cases, so on a normal Mac it skips 4/10 T2 + both finance demo flows, and the rate drops them from the denominator (bench/harness/documents.py, core.py)
4. evals-safety-11 P1: done is not harness-verified (ml/src/brain/orchestrator.py)
5. evals-safety-6 P1: destructive-label gating covers only Messages/Mail/Slack, but web AX feeds page text to the planner (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20, -21, -22, -24.
Note: phase1_main.md val has only 3 ASK items (acc 0.000), so ASK calibration is effectively unmeasured on val; route_v1 must carry it.

## Highest-leverage next moves
- Run decontam over the exact route_dedup.jsonl rows behind main-final and record the sha256 + hits before any route_v1 number (-26).
- Check/reset runs/tinker_guard.state. Gate every Tinker job on live spend + estimate <= cap - lag margin; ~$30 spent on main so far (-23).
- Scope the doc guard to the case's target apps, and report skips in the /43 headline (-25).
- Add a harness-side goal check on done (-11). Extend label gating to web/Electron chat apps (-6).
- Split trace-graded live cases out of the headline, or add readbacks (-24).
