# architect digest - pass 95 (2026-10-25T12:25Z)
Reviewed: main 2de65a9 (unchanged); wip/local a6035fb + 9015e83 (snapshots of local main@2900d4b, not on origin/main): a2004d9 deletes the finance/advisor engines per the user override (AGENTS.md:17-24), forces agentic app routing, drops retrieval/few-shot defaults; 2900d4b rewrites planner_system.md rules and removes worked examples, OCR context every turn for the native-tools planner. No cloud branch moved.
Watch, not filed: ui_only native planner forces OCR context every turn (orchestrator.py:4467-4470@9015e83); per-turn OCR cost unmeasured; tools mode is experimental.
Tests (Linux, wip 9015e83, --timeout=30, test_planner_think.py ignored): 89 failed, 2102 passed, 111 skipped, 2 xfailed; without a timeout the suite hangs.
Open: P0 0, P1 23, P2 13. New: 61, 62, 63 (P1). Closed: 49 (accepted, user override). Re-checked: 48, 51, 53, 54, 55, 57, 58 still open.

## Open P0/P1 (ranked)
1. architect-63: wip suite red (89 failures incl. architect-27 Premiere confirm-timeout safety tests) and hangs.
2. architect-55: failed expects never block on app tasks; finance/advisor and Premiere have no finish criterion.
3. architect-62: finance/advisor demo is planner-only with no verification; AGENTIC_APPS=0 doc is false.
4. architect-61: planner retrieval/few-shot/system prompt changed with no re-measurement; .850/.770 stale.
5. architect-57: destructive gate refuses 'show all files in Downloads', misses 'erase everything on my disk'.
6. architect-58: 'nice work on the demo' treated as a style.
7. architect-54: Slack 'Message #search-team' sends on Enter without confirm.
8. architect-53/51/48, r4 validity (42/44/32/37/40/28/29), Premiere on macOS (26/27/35).

## Next moves
1. Port the safety tests to the planner path and make the suite green with a bounded planner stub before pushing main (63).
2. Hard expects + finish criteria for finance_review/advisor_prep/premiere_edit (55/62).
3. Re-run planner holdouts at k=0 + new system prompt, or keep k=1 (61).
4. Tighten destructive gate, style detector, send-gate exemption (57/58/54).
5. r4 with ROUTER=it2 MEMORY=0 LONGTERM=0, pinned PLANNER/BLIND_PLANNER/PLANNER_MODE=dsl/MUSELET_NO_ESCALATE=1, honest /125.
