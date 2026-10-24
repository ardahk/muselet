# evals-safety digest, pass 14 (2026-10-24T08:32:20Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-23 P1: spend guard at $120/$140. The level-only latch can skip the $120 warning, and the $140 stop leaves $10 against hours of billing lag (tools/review_pulse.sh, tools/tinker_spend.py)
2. evals-safety-25 P1: the cloud/bench document guard inventories all 24 apps (browsers/chat) for 9 cases, so on a normal Mac it skips 4/10 T2 + both finance demo flows, and the rate drops them from the denominator (bench/harness/documents.py, core.py)
3. evals-safety-11 P1: done is not harness-verified (ml/src/brain/orchestrator.py)
4. evals-safety-6 P1: destructive-label gating covers only Messages/Mail/Slack, but web AX feeds page text to the planner (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20, -21, -22, -24.
Checked on cloud/bench 2c57d7f, nothing else material: case-authored close/quit-saving-no teardowns are delegated to id-tracked cleanup. The non-mechanical precondition and inventory errors are counted as SKIP. The time-event case uses a snapshot-diff delete in the bench calendar. HobbyLM/DeskMind runners use the same guard (same scope issue).

## Highest-leverage next moves
- Check/reset runs/tinker_guard.state. Gate every Tinker job on live spend + estimate <= cap - lag margin (-23).
- Scope the doc guard to the case's target apps, and report skips in the /43 headline (-25).
- Add a harness-side goal check on done (-11).
- Extend label gating to web/Electron chat apps (-6).
- Split trace-graded live cases out of the headline, or add readbacks (-24).
