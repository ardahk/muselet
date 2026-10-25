# Lane: test-strategy — why our testing missed what the user found in 10 minutes, and a fix

In one short session the user hit 7 failures our tests had not caught: Clock timer said "set" but Clock showed an
unstarted 15:00; Wikipedia follow-up opened a new tab; "open text edit" -> app not found (STT split the name); Notes
template -> raw AppleScript + confirm + "Script failed"; "Text Caleb ..." swallowed by a pending task; Gmail
(Workspace) reply went to the Mail app; "Forget Everything" in Settings did not stick. Traces: runs/traces/2026-10-24.jsonl
(lead can send excerpts; ask under `## Mac requests`). Branch `cloud/test-strategy`, PR with a report + code.

1. **Postmortem** (`docs/TESTING_POSTMORTEM.md`, <= 2 pages): for each failure, why no test caught it (fakes that
   accept anything, live cases that set up idealised state, Safari/Chrome-only checks while the user's default is Zen,
   no pending-state sequences, STT variants missing, grading on the brain's claim instead of the screen, harness
   timeouts hiding outcomes, etc.).
2. **Acceptance suite** `evals/acceptance.jsonl` + runner support: every demo utterance (pitch/demo_script.md) and every
   user-reported phrasing, as multi-turn live cases with realistic context (Zen default browser, Workspace Gmail,
   apps already open/closed, a pending confirm before the next command, STT-style spelling) and final-state checks
   read from the screen (AX/System Events/files), never from the brain's reply. Lead runs it on the Mac; it gates
   merges that touch the brain.
3. **Offline trace replay**: a tool that replays real user traces (utterance + ctx + recorded observations) through
   the real orchestrator with a recorded-observation fake Hands, so routing/pending-state/arg bugs reproduce on
   Linux. Add the 7 failures as replay regressions (they should fail on today's main).
4. A short "release checklist" in bench/RUNBOOK.md: what must pass before telling the user a feature works.
No Tinker; API <= $10/provider.
