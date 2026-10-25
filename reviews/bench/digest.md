# bench digest — pass 72 (2026-10-25T05:45Z, main@e8023b8)

P0: 0 | open P1: 14 | open P2: 15

Ranked open P1:
1. bench-48 (NEW) the serving few-shot (prompts/planner_fewshot.md:60-85) has the exact oe-spotify-jazz utterance with the full solution, the case's own player-state check and done. The Spotify open-ended result is train-on-test.
2. bench-44 LoRA planner shipped (efd2f3f) on uncommitted numbers. Pooled .731 vs .647; most of the gain is on v2-ho, whose screens were in training.
3. bench-42 acceptance case acc-user-pending-notes-then-text drives Messages with no Messages-not-running guard.
4. bench-36 competitor runs don't pin or record router, planner or serving flags.
5. bench-23 it3 chosen on route_v2, whose gold shares judges and policy with its training labels.
6. bench-31 planner-LoRA demos on v2-holdout screens; the clean 105-row subset was never scored.
7. bench-16 HobbyLM --exclude-kind calc is Muselet-only; calc is now gradable for both.
8. bench-28 5 v2-holdout golds accept field-clobbering type.
9. bench-11, -14, -15, -20, -21, -29 unchanged.

Open P2: -46 (now 5 unevaluated serving switches incl. BLIND_PLANNER), -47, -43, -37, -38, -39, -40, -30, -34, others. Resolved earlier: -41. Withdrawn: -45.

Next moves:
1. Reword the Spotify few-shot goal (different app/genre) or retire oe-spotify-jazz for a paraphrased held-out case (bench-48/-47).
2. Add the Messages-not-running precondition to acc-user-pending-notes-then-text (bench-42).
3. Commit the planner-LoRA eval JSONs, quote pooled numbers, and score LoRA vs base on the 105 clean v2-ho rows (bench-44/-31).
4. ROUTER=it2 on competitor runs; record router, planner, FALLBACK_PLANNER/PLANNER_CONTEXT/APP_HINTS/OPEN_ENDED/BLIND_PLANNER in result rows (bench-36/-46).
5. Re-run base planner holdouts with the new few-shot block; add a blind option to planner_offline.py (bench-46).

Pass 66 notes: main 4150ecb..b340f24 merges test-strategy (bench-42/-43 carried), fix-email-reply, fix-apps-notes, memory-writes, planner-aux/LoRA ship. PLANNER is now another unpinned default for competitor runs: pin PLANNER alongside ROUTER and record both. cloud/open-ended adds APP_HINTS=1 and OPEN_ENDED=1 serving defaults, which change the planner prompt. Re-run planner holdouts with app hints on before merging (same issue as fallback PLANNER_CONTEXT). The planner_offline --app-hints flag exists for that.

Pass 67: main b340f24..dc6f2f5 merges fallback, open-ended, fix-same-tab, fix-pending, hands-clock-verify, design-polish, premiere-demo. NEW P2 bench-46: four prompt/control defaults are on in serving with no planner-holdout re-run. bench-45 WITHDRAWN: both cases are manual:true and skipped by default (my miss in pass 66). bench-42 still unfixed on main. Checked fine: the ocr_screen predicate (screenshot + OCR, errors fail the check), and the premiere cases (Premiere-not-running precondition, a copied run project, and a negative-routing case with forbids). run_typed_decisions.sh only changes which Python interpreter runs it.

Pass 68 (no new findings, no status changes): main 82c9810 only changes orchestrator blind-AX detection, so CEF apps like Spotify go to screenshot + grounder. No bench/eval/serve_brain files changed, so all open findings stand as of pass 67 (bench-42 still unfixed). wip/local = main. premiere-route-fix touches orchestrator and tests only. Watch: blind-AX now routes more steps to the grounder, so planner step latency in live runs may rise for CEF apps; quote live step p50 per app.

Pass 69 (no new findings, no status changes): main unchanged, all open findings stand. Watch wip/local c156d18 (unmerged; orchestrator only). (a) The new _PREF_VAGUE rule rejects the planner's first-turn `ask` whenever the goal contains some/any/something/whatever. Its comment quotes evals/open_ended.jsonl utterances ('play some jazz', 'add something to cart'), so open_ended results after this lands are tuned on those cases: report them as tune, not held-out. It would also reject an ask in 'text someone ...' style goals; confirm still gates sends. (b) Planner context now drops screen text when the goal targets another app, and labels it 'data only, never instructions'. That's a good prompt-injection hardening, and it changes the planner prompt again (bench-46).

Pass 70: main e425cad merges the wip change watched in pass 69 (PR #86). NEW P2 bench-47: the open-ended ask guard is fitted to evals/open_ended.jsonl cases, so label results after it as tune and add paraphrased held-out asks. The screen-context gating (data-only label) is good hardening, and it is another serving planner-prompt change (bench-46). No bench/eval/serve_brain changes; all open findings stand (bench-42 unfixed). wip/local 80c871c has no changes in my lane.

Pass 71 (no new findings, no status changes): main unchanged, all open findings stand. Watch wip/local 323d274 (on local c711320, unmerged): it adds BLIND_PLANNER=base as a serving default, so the base planner takes blind/open-ended/fallback tasks with batch cap 2 and finish_when. It also adds blind examples to prompts/planner_fewshot.md. That changes the PLANNER=base reference prompt behind the .786/.917/.608 row, and adds a fifth unevaluated serving switch (bench-46). Before merging, re-run the base planner holdouts on the new few-shot and record BLIND_PLANNER in bench result rows. Also, the new few-shot examples use the exact open-ended eval utterance "play some jazz on Spotify" (oe-spotify-jazz) twice, including a worked done. If this merges, that case is a train-on-test result; extend bench-47 and drop it from or reword it in the open-ended suite.

Pass 72: main e425cad..e8023b8 merges PR #87 (blind planner) and #88 (blind typing, Swift only). NEW P1 bench-48 (see above). bench-46 updated with BLIND_PLANNER. cloud/agentic-loop 9b2e512 (unmerged) adds a finish-criterion done gate, a page-load re-poll that won't count against the loop guard, workflow filtering and a cross-app retrieval skip. The done gate is stricter (good against false done). Retrieval changes alter planner prompts again, so re-run holdouts on merge. Its tests use user-trace utterances, not eval cases. wip/local 20055d1 has no changes in my lane.
