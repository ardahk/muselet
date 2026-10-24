# evals-safety digest, pass 16 (2026-10-24T09:03:00Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-26 P1: the main-final checkpoint was trained from the stale route_dedup.jsonl with no decontam record. The it2 plan acknowledges the staleness, but no stamp exists yet (training/src/muselet_train/datums.py)
2. evals-safety-27 P1: it2 go/no-go criteria (H1-H8) are gated on per-label route_v1 results, which turns the measurement of record into a dev set (training/reports/phase1_it2_plan.md)
3. evals-safety-23 P1: spend guard at $120/$140. The level-only latch can skip the $120 warning, and the $140 stop leaves $10 against hours of billing lag (tools/review_pulse.sh, tools/tinker_spend.py)
4. evals-safety-25 P1: the cloud/bench document guard inventories all 24 apps for 9 cases, which skips 4/10 T2 + both finance demo flows and drops them from the denominator (bench/harness/documents.py)
5. evals-safety-11 P1: done is not harness-verified, only expect/fresh-observe gated (ml/src/brain/orchestrator.py)
6. evals-safety-6 P1: destructive-label gating covers only Messages/Mail/Slack (ml/src/brain/orchestrator.py)

Open P2: -8, -12, -17, -20, -21, -22, -24.
Checked on main bb494af (brain-3/finance-3/advisor-3 merged), nothing else material: 455 non-MLX ml tests pass (10 files need mlx/PIL). router_check fits tau on parity/val, not route_v1. The bench typed_decisions normalization is recorded per answer.

## Highest-leverage next moves
- Gate it2 on val only. Score route_v1 once on the chosen candidate (-27).
- Record decontam hits + sha256 for every training file behind a reported checkpoint (-26).
- Check/reset runs/tinker_guard.state. Gate it2 launch on live spend + estimate <= cap - lag margin (-23).
- Scope the doc guard to the case's target apps, and report skips in the /43 headline (-25).
- Harness-side goal check on done (-11). Label gating for web/Electron chat apps (-6).
