# bench digest — pass 83 (2026-10-25T09:00Z, main@4f94e42)

P0: 0 | open P1: 14 | open P2: 21

Ranked open P1:
1. bench-44 LoRA planner shipped (efd2f3f) on uncommitted numbers. Pooled .731 vs .647; most of the gain is on v2-ho, whose screens were in training.
2. bench-42 acceptance case acc-user-pending-notes-then-text drives Messages with no Messages-not-running guard.
3. bench-36 competitor runs don't pin or record router, planner or serving flags.
4. bench-23 it3 chosen on route_v2, whose gold shares judges and policy with its training labels.
5. bench-31 planner-LoRA demos on v2-holdout screens; the clean 105-row subset was never scored.
6. bench-16 HobbyLM --exclude-kind calc is Muselet-only; calc is now gradable for both.
7. bench-28 5 v2-holdout golds accept field-clobbering type.
8. bench-11, -14, -15, -20, -21, -29 unchanged.

Open P2: -50 (NEW: timer-cancel/cart finish evidence passes on absence), -52 (NEW: cache-dependent 35B blind/agentic planner default), -49 (NEW: Finish-when line reaches the LoRA planner, out of its SFT distribution), -46 (now 5 unevaluated serving switches incl. BLIND_PLANNER), -47, -43, -37, -38, -39, -40, -30, -34, others. Resolved: -41, -48 (pass 74), -51 (pass 77). Withdrawn: -45.

Next moves:
1. Gate Finish-when to the base/blind planner, or A/B the LoRA with and without it (bench-49); add paraphrased held-out open-ended asks (bench-47).
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

Pass 73: main e8023b8..fe2de69 only makes serve_brain.sh use the local grounder copy models/grounding/eyes-4b-mlx when present, instead of a lazy HF download of deskmind/eyes-4b@mlx-4bit. Not verified: the local folder is gitignored and has no recorded revision, and the grounding README downloads to a different path (models/eyes-4b-mlx). Record the source revision so grounder bench numbers map to the served weights. NEW P2 bench-49 (Finish-when reaches the LoRA planner). bench-48 still open. Watch wip/local 422399a (on local b43270d, unmerged): the Spotify few-shot still uses the exact oe-spotify-jazz goal and now solves it with `tell application "Spotify" to play`, so bench-48 is unchanged. It also adds timer Finish-when criteria and regenerates training/artifacts/planner_lora_render_samples.jsonl (the token parity reference). Confirm the regenerated render still matches the SFT training render, not just the new serving prompt.

Pass 74: main fe2de69..e2f7e5e merges agentic-loop (31e500a, 9b2e512, dc7a063), fix-thinking (b43270d), premiere-route-fix and the timer controls (a615f00). bench-48 RESOLVED: the Spotify few-shot is now a YouTube example, and no eval case matches. bench-49 still open (Finish-when at orchestrator.py:3816-3820, now with timer criteria). The finish-criterion done gate is stricter against false done, which is good. Retrieval now skips other-app demos and filters workflows, another planner-prompt change for bench-46. Watch cloud/agentic-apps 523d2c1 (unmerged): it adds AGENTIC_APPS=1 as a serving default, which sends app-kind skills (start_timer, create_event, send_message, compose_email, play_music, premiere_*) to the planner instead of System-1 skills. That changes latency and pass semantics for HobbyLM, DeskMind, live and acceptance cases that route to those skills, and router accuracy no longer describes what executes. On merge, pin AGENTIC_APPS on competitor runs, record it in result rows, and report per-case latency for off vs on. wip/local 3f8e2f8 has no changes in my lane.

Pass 75 (no new findings, no status changes): main and wip/local unchanged, all open findings stand. cloud/agentic-apps 1904638 merges main and removes timer_control (router:false, so no router-eval impact). Checked fine: planner-driven sends under AGENTIC_APPS go through a confirm. That covers a pressed Send button, enter/cmd+return when enter sends, and type+enter. The confirm summary is re-derived when it doesn't name the recipient. cmd+shift+d is in _DANGEROUS_COMBOS, and scripts go through script_needs_confirm. The agentic-apps watch from pass 74 (pin and record AGENTIC_APPS, report off vs on latency) still applies on merge.

Pass 76: main e2f7e5e..de1070d merges agentic-apps (AGENTIC_APPS=1 is now a serving default, so app skills run through the planner) and f30bf1d autodone. NEW P2 bench-50 and bench-51. The AGENTIC_APPS watch now applies to main: pin and record it on competitor runs, and report off vs on latency. Router-accuracy claims describe routing, not what executes for app-kind skills. The new branches (agentic-evidence c4703c4, app-knowhow fc92f6b, browser-flow c0421e6) touch orchestrator/finish/app_hints/tests only. app-knowhow changes app_hints tips again, another planner-prompt change for bench-46. agentic-evidence unifies evidence() for done and auto-done: re-check bench-50 there on merge.

Pass 77: main de1070d..3a0860c. bench-51 RESOLVED (symlinks untracked). NEW P2 bench-52: BLIND_PLANNER becomes escalate (35B-A3B, think 512) whenever the 35B is in the HF cache, so the served planner for blind/agentic/app tasks is machine-dependent, unmeasured and unrecorded. bench-50 still open, and the same rule is on agentic-evidence 1918cad. app-knowhow c69dfec changes only app_hints tips (bench-46). browser-flow 485763f is merged-main plus orchestrator same-tab work. wip/local = main.

Pass 78 (no new findings): main 3a0860c..cf33215 merges agentic-evidence, app-knowhow, browser-flow, obs-labels and control-labels. bench-50 is now on main: the unified evidence() still treats 'no Pause/Resume' as a cancelled timer for both auto-done and the done gate. app-knowhow rewrites app_hints tips (another planner-prompt change, bench-46). The Swift obs-labels change adds derived labels for unlabeled controls, which changes observation text for all planners (bench-46/-49: the LoRA SFT render predates it). No bench/eval/serve_brain changes. bench-42, -44 and -36 are still unfixed. wip/local = main.

Pass 79 (no new findings): main cf33215..cef8797 sends agentic app tasks and timer controls to the blind/agentic planner (35B when cached). bench-52 updated: docs-final itself quotes 6.0 s step p50 for that planner, against the 3 s gate. cloud/docs-final bf9118d (unmerged) is largely candid: DeskMind leads System One (.831/.658 vs .779/.622), no valid HobbyLM score, DeskMind Bench not run, agentic build unmeasured. But it still headlines the LoRA as 'holdout mean .850' (unweighted; pooled is .731, and the gain is concentrated on contaminated v2-ho screens: bench-44/-31/-30). Before merge: quote the pooled number, or add the contamination caveat next to .850. wip/local c86fec4 has no changes in my lane.

Pass 80: 1 new finding (bench-53, P2, cloud/agentic-fixes2 b9cd089): YouTube play evidence accepts any watch?v= URL, including the brain's own last url action, with no subject or player-state check. Before it merges, use only the observed URL and require the subject in the title. Main cef8797..73b8031:
- Adds a Spotify few-shot "play boyle iyi on Spotify". No eval or bench case uses that wording (grep), so bench-48 doesn't regress.
- Spotify play evidence now requires the current track name to contain the subject. Good positive evidence.
- PLANNER=35b is a new explicit option, but the default blind planner is still picked by cache state (bench-52 open).
- The few-shot, app-hint and observation changes add to bench-46.
- bench-50 (timer cancel) is unchanged on main and on agentic-fixes2.
wip/local b8eeec4 differs only in Observe.swift.

Pass 81 (no new findings, no status changes): main still 73b8031. agentic-fixes2 104a411 is a merge of main; bench-53 unchanged. wip/local 51d833a has no diff from main.

Pass 82, 2 new findings:
- bench-54 (P1): the merged Devpost text headlines the LoRA as 'mean .850 vs .770' without the pooled .731 or the v2-ho contamination caveat. Fix before the 09:00 PDT submission.
- bench-55 (P2): ab850b3 makes planner expects soft on agentic tasks and raises the budget to 30 turns / 300 s, so done rests on the weak finish evidence (bench-50/53).
Also: bench-53 is now on main (agentic-fixes2 merged). bench-52: PLANNER=35b also sets 350 observe nodes. wip/local e03e2c8 has no diff from main.
Next moves: (1) fix the Devpost planner wording; (2) tighten timer-cancel and YouTube evidence; (3) gate bench-42; (4) pin and record ROUTER=it2, the planner, BLIND_PLANNER, AGENTIC_APPS and MUSELET_OBS_NODES on competitor runs; (5) commit the LoRA eval outputs.

Pass 83: 1 new finding (bench-56, P2, cloud/cool-tasks): summary_note evidence passes on any open Notes note with 15+ words. Before merge, require a new note and a link to the source.
- bench-53 is partly mitigated by 2c0430e (must be on a YouTube page); subject and stale-URL gaps remain.
- Main sendgate 05d42d2: find/search fields no longer count as send targets. Looks fine; a composer label containing 'search' or 'find' would skip confirm (unverified, low risk).
- native-tools: PLANNER_MODE=tools is opt-in (default dsl). If used in benchmarks, record it in result rows.
- cool-tasks adds broad app-hint triggers ('place', 'restaurant', 'summarize', 'temperature'): more prompt drift for bench-46.
- ui-progress is UI only. wip/local 52eb571 has no diff from main.
- bench-54 (Devpost .850) is unchanged on main.
