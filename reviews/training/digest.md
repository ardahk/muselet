# training review digest: pass 16
_heads: cloud/data-pipeline 70b7d1b (iteration 2: ask_rule, finance_check, it2 top-ups, hypotheses); main bb494af (router_check, decisions builder brief); bench f584cb2 and wip/local c85a000 have nothing in my lane_

## Open P0/P1 (ranked)
- **training-23** [P0] The main run was trained and evaluated on the stale pre-fix route_dedup.jsonl. It is acknowledged and v2it2 is planned; the external-decontam status of the stale file is still unanswered, and router_check runs main (`training/reports/phase1_it2_plan.md`).
- **training-5** [P1] Two Tinker spenders now share about $81 of headroom; both use per-run guards and billing lags (`cloud/builder_decisions.md`, `train.py`).
- **training-26** [P1] ask_rule relabels unclear-referent ASK ("send it to him") as a concrete skill (`training/src/muselet_train/ask_rule.py:67-74`).
- **training-27** [P1] Iteration 2 tunes data against route_v1, so it is no longer held-out (`training/reports/phase1_it2_plan.md:24-31`).
- **training-28** [P1] media_control and premiere_command conflict on the same playback words in Premiere (`training/src/muselet_train/contexts.py:55-65`).
- **training-24** [P1] The router almost never ASKs; a fix is in progress (`datums.py`).
- **training-25** [P1] media_control, dark_mode and find_file are weak; top-ups are in progress (`gen.py`).
- **training-14** [P1] main has catalog v2 but 36-option parity samples (`training/artifacts/route_render_samples.jsonl`).
- **training-8** [P1] No per-label 15% A1 STOP gate (`adjudicate.py`).
- **training-15** [P1] The teacher subset skews the label prior (`teacher.py`).
- **training-11** [P1] Finder selection semantics (`contexts.py`).

Open P2: training-9, -10, -12, -13, -18, -19, -20, -22.

## Highest-leverage next moves
1. Before launching v2it2: treat pronoun values as missing in ask_rule.verdict (training-26) and keep media_control out of Premiere (training-28), since both are one-line changes.
2. Freeze a fresh held-out route set and confirm H1-H8 on val; quote route_v1 as dev from now on (training-27).
3. Set one shared ledger: each worker's --max-usd is at most 150 minus billed minus every unbilled estimate from both workers (training-5).
4. Don't quote main's route_v1 numbers or router_check tau; re-run router_check on the v2it2 parity file (training-23).
5. Report decontam counts for v2it2, including the it2 top-ups, in the it2 report (training-10).
