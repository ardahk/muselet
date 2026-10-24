# evals-safety digest — pass 27 (main@7147694)

Open: P0 0 · P1 6 · P2 7

## Open P0/P1 (ranked)
1. **-25** live document guard skips 9/43 cases (any Chrome/Slack/Messages window) and drops skips from the denominator; calendar-probe failure adds another skip. bench/harness/documents.py, bench/live/run_live.py.
2. **-30 (NEW, cloud/grounder-wire afb12a6, unmerged)**: grounded `click "<target>"` confirms only if the planner's description contains a danger word. "the paper plane icon" clicks Send with no confirm on blind (empty-AX/canvas) windows; the grounder is on by default. orchestrator.py:1319-1336.
3. **-6** Enter-to-send confirm fallback still only covers Messages/Mail/Slack (orchestrator.py:1118@main).
4. **-11** `done` accepted after a passed expect or a fresh observation; no harness final-state check.
5. **-26** main-final near-dups: 37/140 route_v1 and 10/43 live_t1. pitch-3 reports on route_v1_clean with disclosure (unmerged); main serve_brain.sh:6 still cites full-set r2 1.000; no live_t1 clean subset.
6. **-23** spend guard latch plus billing lag ($34.60 MTD per pitch-3; $140 stop leaves $10 headroom).

P2: -8, -12, -20, -21, -22, -24, -28.

## Next moves (max 5)
1. Before merging grounder-wire: confirm grounded clicks on blind windows when the goal or app is send/delete-like (-30).
2. Count skips in the live denominator, or narrow the document guard to the case's own apps (-25).
3. Merge pitch-3, and add a live_t1 clean subset or caveat; fix the serve_brain.sh:6 comment (-26).
4. Check or reset runs/tinker_guard.state before the it2/decisions runs (-23).
5. Extend the Enter-confirm app list to Discord/WhatsApp/Teams/web composers (-6).

Pass 27 also checked, nothing material: main generic_decide single MLX thread; planner holdout-2 (opt-in, written after holdout-1 was used to derive rules 16-18; pitch-3 holdout .57 should say which prompt it used); data-pipeline it2 report (non-candidate, fails evalcheck: 8 pairs, so the gate works).
