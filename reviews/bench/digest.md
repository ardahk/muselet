# bench digest — pass 68 (2026-10-25T04:40Z, main@82c9810)

P0: 0 | open P1: 13 | open P2: 14

Ranked open P1:
1. bench-44 LoRA planner shipped (efd2f3f) on uncommitted numbers. Gain is on v2-ho, whose screens were in training. Pooled .731 vs .647, not 'mean .850'.
2. bench-42 acceptance case acc-user-pending-notes-then-text (now on main) drives Messages with no Messages-not-running guard.
3. bench-36 competitor runs not pinned to it2 though claims say "it2 only"; router not recorded in results.
4. bench-23 it3 chosen on route_v2, whose gold shares judges and policy with its training labels.
5. bench-31 planner-LoRA demos on v2-holdout screens; clean 105-row subset never scored (now the serving planner).
6. bench-16 HobbyLM --exclude-kind calc is Muselet-only; calc now gradable for both (bench-41 resolved).
7. bench-28 5 v2-holdout golds accept field-clobbering type.
8. bench-11, -14, -15, -20, -21, -29 unchanged.

Resolved this pass: bench-41 (provenance ok at b340f24). Downgraded: bench-34 to P2 (serving planner is LoRA THINK=0). New P2: bench-45 (cloud/open-ended Slack status / Amazon cart without user_ok or restore). Other P2: -37, -38, -39, -40, -43, -30, ...

Next moves:
1. Add the Messages-not-running precondition to acc-user-pending-notes-then-text (bench-42).
2. Commit the planner-LoRA eval JSONs, quote the pooled pass, and score LoRA vs base on the 105 clean v2-ho rows (bench-44/-31).
3. ROUTER=it2 on competitor runs; record router, planner and the FALLBACK_PLANNER/PLANNER_CONTEXT/APP_HINTS/OPEN_ENDED flags in result rows (bench-36/-46).
4. Rebuild calc_checker and grade calc for both systems; drop --exclude-kind calc (bench-16).
5. Record forced_releases per case; disclose r4 D04-D06 fixed after observation (bench-38/-39).

Pass 66 notes: main 4150ecb..b340f24 merges test-strategy (bench-42/-43 carried), fix-email-reply, fix-apps-notes, memory-writes, planner-aux/LoRA ship. PLANNER is now another unpinned default for competitor runs: pin PLANNER alongside ROUTER and record both. cloud/open-ended adds APP_HINTS=1 and OPEN_ENDED=1 serving defaults, which change the planner prompt. Re-run planner holdouts with app hints on before merging (same issue as fallback PLANNER_CONTEXT). The planner_offline --app-hints flag exists for that.

Pass 67: main b340f24..dc6f2f5 merges fallback, open-ended, fix-same-tab, fix-pending, hands-clock-verify, design-polish, premiere-demo. NEW P2 bench-46: four prompt/control defaults are on in serving with no planner-holdout re-run. bench-45 WITHDRAWN: both cases are manual:true and skipped by default (my miss in pass 66). bench-42 still unfixed on main. Checked fine: the ocr_screen predicate (screenshot + OCR, errors fail the check), and the premiere cases (Premiere-not-running precondition, a copied run project, and a negative-routing case with forbids). run_typed_decisions.sh only changes which Python interpreter runs it.

Pass 68 (no new findings, no status changes): main 82c9810 only changes orchestrator blind-AX detection, so CEF apps like Spotify go to screenshot + grounder. No bench/eval/serve_brain files changed, so all open findings stand as of pass 67 (bench-42 still unfixed). wip/local = main. premiere-route-fix touches orchestrator and tests only. Watch: blind-AX now routes more steps to the grounder, so planner step latency in live runs may rise for CEF apps; quote live step p50 per app.
