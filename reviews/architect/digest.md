# architect digest - pass 81 (2026-10-25T07:40Z)
Reviewed: main cf33215, which merges browser-flow, app-knowhow and agentic-evidence (all reviewed in pass 80), plus mac/obs-labels 6d8d7bb (derived labels for unlabeled controls) and #99 control-labels 37e6459 (value= on dials; digits typed into sliders/steppers with an arrow-key fallback). wip/local 11da94c is the same tree as main.
Tests (Linux): main agentic/finish/evidence/catalog/planner/fallback/grounder/same-tab/app-hints: 347 passed. The Swift changes were reviewed by reading only (no macOS compile or run).
Open: P0 0, P1 16, P2 10. New: architect-52 (P2). 48, 49 and 51 re-checked: still open on cf33215.

## Open P0/P1 (ranked)
- architect-51 [P1] (new) BLIND_PLANNER defaults to 35B-A3B + THINK 512 whenever its HF cache exists: unmeasured, ~5-7 s/step vs 3 s gate, +19 GB
- architect-48 [P1] Timer-control pre-route hijacks 'set a timer ... to stop the oven' into a cancel (main de1070d)
- architect-49 [P1] agentic-apps on by default on main: start_timer/create_event and 10 more go through the planner, unmeasured (38/125 r4)
- architect-45 [P1] Shipped LoRA planner's holdout .850 rests on a decontam gate that misses word-order paraphrases of holdout goals
- architect-44 [P1] Benchmark memory isolation misses working memory: cross-case rewrites in sealed runs, shared working.json
- architect-42 [P1] 13d0486 drops start-state screenshot capture: 20/125 r4 cases (screenshot+none) crash at final snapshot
- architect-40 [P1] Sealed HobbyLM r4 failures patched post-hoc; any r4 rerun is tuned-on-test
- architect-37 [P1] it3 now default router; sealed-set overlap check not recorded for it3
- architect-33 [P1] Done verifier ships on by default with an unfitted 0.5 threshold
- architect-32 [P1] HobbyLM replay drops skips from denominator; claim template says /125
- architect-29 [P1] No competitor benchmark number exists
- architect-28 [P1] Retrieval bank holds paraphrases of v2-holdout goals; ship gate inflated
- architect-27 [P1] premiere_command sends shortcuts without Timeline focus, always reports success
- architect-26 [P1] Planner prompt teaches cmd+t as Premiere default transition (Mac: cmd+d)
- architect-13 [P1] Cloud Tinker System One backend reports as 'muselet', untagged
- architect-8 [P1] Phase-1 LoRA likely misses Sat 12:00 PDT; no fallback router measured

Watch (not filed): typeIntoControl (Act.swift@cf33215) clicks the control's midpoint if AX focus fails, then posts digits and up to 70 arrow keys as global keystrokes, with no check that focus actually landed on the control. A wrong focus sends digits or arrows to whatever is focused. The loop stops after the first press that doesn't change the value, so at most one stray arrow press.

## Next moves (max 5)
1. architect-51: give BLIND_PLANNER a fixed default (no cache probe), and measure escalate vs base vs LoRA on the blind/agentic slices.
2. architect-48/49: fix the timer-control match, and default AGENTIC_APPS=0 or measure on vs off; pin both settings in r4 configs.
3. architect-42: restore the screenshot start-state, then smoke-test one calc, one screenshot and one none case on the Mac.
4. Run HobbyLM r4 with ROUTER=it2 MEMORY=0 LONGTERM=0 and the knobs pinned, and report passes/125 with skips and timeouts counted as failures (architect-32/37/40/44).
5. architect-52: record ax_ms on a large Chrome page before and after obs-labels, and limit the sibling scan by role and count.
