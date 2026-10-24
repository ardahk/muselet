# evals-safety digest, pass 10 (2026-10-24T07:40:54Z)

## Open P0/P1 (ranked)
No open P0.
1. evals-safety-11 P1: done is not harness-verified; partial on main 4a74659 (ml/src/brain/orchestrator.py)
2. evals-safety-6 P1: confirm gaps for non-Apple chat apps' Enter/Send (ml/src/brain/orchestrator.py)
3. evals-safety-4 P1: 'no' string is truthy, so ctx online renders as yes (ml/src/brain/decision.py:236)

Open P2: -8, -12, -17, -20 (grounding first-N), -21 (mem_guard kills :8766 = Premiere bridge port), -22 (script test covers the dead weak policy; `open (POSIX file` paren bypass).
Resolved this pass: -2 (script bypasses fixed on main), -14 (mute), -16 (HobbyLM frozen data tracked; 31/31 SHA-256 match PROVENANCE), -19 (HobbyLM scored by the shared strict_pass).
Checked: main 251 non-MLX brain/finance/advisor tests pass; cloud/bench 50 tests pass; data-pipeline phase1_fixes report decontaminates against 570 external utterances (reported 0 residual matches; the data files aren't in the repo, so I didn't verify that myself). wip 85c73ed drops a bare yes/no after confirm_cancel (good).

## Highest-leverage next moves
- Add a harness-side goal check on done (verify RPC or the task's expect) before success (-11).
- Delete the dead module-level script_needs_confirm and test the real method with the bypass probes (-22).
- Normalize ctx online to a bool at the protocol boundary (-4).
- Move the bench brain off :8766 before Premiere bridge work lands (-21).
