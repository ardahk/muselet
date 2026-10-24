# evals-safety digest, pass 9 (2026-10-24T07:25:19Z)

## Open P0/P1 (ranked)
1. evals-safety-2 P0: script confirm bypasses (System Events click, Safari JS/open location, «event»). Open on main d8ad966; fixed on cloud/brain-2 741465c, pending merge (ml/src/brain/orchestrator.py)
2. evals-safety-19 P1: HobbyLM rerun scored by its own 'completed', Muselet by strict final state (bench/hobbylm/replay.py)
3. evals-safety-14 P1: bool 'on' override inverts mute. Open on main; fixed on brain-2 (ml/src/brain/orchestrator.py)
4. evals-safety-11 P1: done not harness-verified; partial on brain-2 (ml/src/brain/orchestrator.py)
5. evals-safety-16 P1: HobbyLM frozen task files gitignored (.gitignore on cloud/bench)
6. evals-safety-6 P1: confirm gaps for non-Apple chat apps; web AX now exposes more page text (ml/src/brain/orchestrator.py)
7. evals-safety-4 P1: 'no' string is truthy, so ctx online renders as yes (ml/src/brain/decision.py:236)

Open P2: -8, -12, -17, -20 (grounding first-N sampling), -21 (mem_guard kills :8766 = Premiere bridge port).
Resolved this pass: -10, -15 (decontam reads external `text`; 753 eval utterances), -18 (pitch claims scoped).
Checked and clean: advisor-2 0a65f75 (truth.json reserves restructure keeps the same values, excess 68,480; 5 opportunities; never deletes user sheets/notes; 172 tests pass). finance-2 dfaf785 (fixtures unchanged since f4ae461, 184 tests pass). main d8ad966 adds evals/external (main has no training/ code to break).

## Highest-leverage next moves
- Merge cloud/brain-2 before the demo build: it closes -2 and -14 on main and narrows -11.
- In brain-2's block regex, also catch `open (POSIX file ...)` with parentheses.
- Score the HobbyLM rerun with the same final-state grader as Muselet (-19), and un-ignore bench/hobbylm/upstream/data (-16).
- Normalize ctx online to a bool at the protocol boundary (-4).
