# W10: Report, pitch and demo (due Sun Oct 25, 09:00 PDT)

Repo `ardahk/muselet`. Read `docs/REPORT.md`, `pitch/claims.md` and `docs/HANDOFF.md` §2 and §10.

## Rules
- Every number in the pitch has a source: a run dir, file or HF revision. A pending number stays out of the pitch.
- Report holdout (not tune) numbers. Report skips and harness timeouts. Disclose contamination checks (§1b of
  `pitch/claims.md`).
- Compare like for like: same Mac and harness where possible. Label "published" numbers as theirs.

## Steps
1. After W8's runs, update:
   - `docs/REPORT.md` §4–5: live suite block 2, HobbyLM r4 Muselet vs published 90/125 (and the rerun if done),
     DeskMind diag if run;
   - `pitch/claims.md`: the planner numbers .88 / .643 / .667 (some rows still show .84 / .57); grounding and OCR
     run paths.
2. After W1/W2: router it3 and decisions LoRA tables, with costs.
3. **Demo script** (3 minutes; segments from `AGENTS.md`):
   - (a) instant system commands with the latency chip (volume/dark mode/compound);
   - (b) messaging a real contact with the confirm;
   - (c) Gmail draft in Zen;
   - (d) Numbers finance review (duplicates + receipts);
   - (e) advisor prep;
   - (f) a safety moment: an injected on-screen instruction refused, or a permission prompt it asks about.
   Rehearse each through the real app on the Mac; record the takes' latencies from traces.
4. A capability list for judges, with what is measured vs. demo-only.

## Acceptance
REPORT.md and claims.md are consistent with each other and with the run dirs; the demo is rehearsed twice end to
end.
