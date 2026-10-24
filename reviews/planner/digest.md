# planner lane — pass 46 (main 806b0d4, wip 6b1006e, planner-verify c9de7aa, planner-think 6d14a7a, w9 6aa332a)

Open P0: none.

Open P1 (ranked):
0. planner-40: planner-verify accepts done after any successful skill, skipping the model check (ml/src/brain/orchestrator.py on cloud/planner-verify)
1. planner-30: JXA string-concat doShellScript bypasses script confirmation (ml/src/brain/orchestrator.py). Fixed on w9-safety (PR #46), still open on main.
2. planner-31: Rule 14 'expect focused' (no ref) is rejected by HandsKit before acting (prompts/planner_system.md)
3. planner-38: Planner LoRA trained without few-shot/retrieval, but served with both by default (training/planner_lora/common.py, tools/serve_brain.sh)
4. planner-15: read-only Numbers scripts still trigger CONFIRM (ml/src/brain/orchestrator.py). Not fixed by w9.
5. planner-32: open_folder catalog lacks 'view', so demo 1 goes through the planner (skills/catalog.json)
6. planner-28: compose_text types model text with no sendgate (ml/src/brain/tools/compose_text.py). Exposure grows with it3.
7. planner-24: Calculator keys posted before Calculator is frontmost (ml/src/brain/orchestrator.py). Fixed on w9 4bbb6d8.
8. planner-29: v2 bench goals near-duplicate the few-shot examples (evals/planner_v2_*)
9. planner-6: premiere_command unimplemented; catalog args mismatch the UXP bridge (app/Sources/HandsKit/Skills.swift)

Highest-leverage next moves:
- planner-verify: before merging, drop the skill-ok = done-evidence rule (planner-40). Keep the decide-based verify, which also takes care of most of planner-33.
- Before any LoRA ship call, evaluate the adapter under the exact serve flags (few-shot, RETRIEVAL_K, THINK), or serve it with `--planner-fewshot none` and RETRIEVAL_K=0 (planner-38).
- Merge w9-safety, but first narrow `\[` to JXA computed keys and drop `\\`, `set .* to` and `format` for Numbers targets (planner-37, planner-15).
- Add `view` to open_folder in catalog.json and to the prompt example (planner-32). Fix rule 14 to say `expect focused #<ref>` (planner-31).

Pass 46 notes:
- main and wip only add the memory_followups denylist in plan_bank (fine) and a brain-9 brief (named browser for open_url/web_search, OCR wait for web answers, planner warmup).
- planner-verify has one issue, planner-40. Otherwise its done verification follows the brief: a fresh observe, OCR when the text is short, a bool decide on the inline planner weights (VERIFY_P 0.5), MAX_RECOVERY 2, and an honest "Not finished: ..." reply. The cost when there is no expect is one observe, possibly a screenshot+OCR, one decide prefill (~1.5-3k tokens) and, if the answer is no, a 24-token missing-text decode. That is my estimate; I did not measure it. It should fit the 3 s/step gate.
- planner-think adds a bounded think block. It is off by default (THINK=0). The cache and feed handling looks right: the last sampled token is fed before </think> on every close path. With thinking on, TTFT for the first streamed action grows by the think budget.
- w9 6aa332a scopes `appears` to the focused window plus its sheets and menus, and matches word-bounded. That is stricter; the prompt examples still fit. The permission gate now uses the post-action state, outside this lane.
- memory-lt f0ea345 (WIP) adds long-term memory rows (up to 3) to the planner's dynamic prompt. The rows are not framed as data. I have not verified where they come from: if they can contain screen text, they are an injection surface. I'll re-check once it is out of WIP.
- hands-clock and decisions don't touch planner paths.

Pass 45 notes: main ebdd639 adds briefs only (planner-think, planner-verify, hands-clock, docs-demo, live-cases) and an AGENTS rule that planner steps may take a few seconds (p50 <= 3 s/step). wip/local has the same lane files as main. On w9-safety, the done-evidence commits were reverted, the Calculator frontmost gate fixes planner-24, and control/format characters in a script now force a confirm (fine). Trash resolution now requires an exact match, and installed apps are preferred over the site rewrite; I found no lane issues in those. memory/memory-lt adds working memory: a guarded LLM rewrite (the irreversible-verb guard blocks newly added send/delete/etc.), direct execution of safe skills only, and a `Recent:` block in the planner's dynamic message, so the static cache is intact. Screen text reaches the rewrite only as the URL's site, not the window title. Its one issue is planner-39 (latency). planner-lora gives planner-38. router-it3-serve widens planner-28. docs-demo and ui-polish don't touch this lane.

Pass 44 notes: main and wip/local don't change any lane files (main adds briefs only). w9-safety 50a3b25 does two things. It hardens _SCRIPT_BLOCK and target extraction, which fixes planner-30 but introduces planner-37 (false confirms on Numbers reads). It also resets _batch_confirmed after every non-confirm action, so a confirm covers only the very next action; that is stricter and fine, and planner-35 is unchanged. memory-eval adds memory_followups to the plan_bank decontamination denylist, which is good. memory doesn't touch this lane.

Pass 43 notes: main 3876f3a..3772f7c in this lane is the comms channel redirect (compose_email/draft_email become send_message for messaging goals; planner `open Mail` is a terminal failure), the Clock hint, timers RPC, and k=1 plan_bank retrieval. Retrieval leakage was reviewed in pass 41: quote only v2-holdout. I found no new issues in that diff. The new findings come from re-walking demos 1 and 3 through the prompt, the DSL, the executor and HandsKit. wip/local has the same lane files as main. No cloud/* branch changed lane files since pass 42. I re-checked planner-24/26/27/28/6/25/29: the code is unchanged, so they stay open.


Pass 42: no new findings. comms-2 sends requests that name a message channel (text/message/iMessage/SMS, unless mail/email is also named) to comms.start, through the router, the slot step, the planner skill step and ask. It relabels compose_email/draft_email as send_message, and the planner can't open Mail for a texting goal. Sending still needs a confirmation that shows the recipient and an excerpt (comms.py L582-602) and checks that Messages is frontmost. c65ee70 makes the verb-first form require a message noun. clock-timers only adds the one-time Clock-shortcut hint and the reply wording. main changed only HandsKit Contacts/MessagesCompose v2 and WindowsProbe; messages_send still posts a single Return after re-checking the window. Open findings are unchanged: planner-28, planner-24, planner-29, planner-6 (P1); planner-26, planner-27, planner-25 (P2).


Pass 41: no new findings. planner-retrieval plan_bank.py draws its BM25 demos from v2-tune and excludes the v1 tune/holdout/holdout2, v2-holdout, live_t1 and external goals (L187-208). Holdout results stay clean, but v2-tune scores are inflated once retrieval is on, so quote only v2-holdout for retrieval comparisons. I only skimmed comms-2 and clock-timers this pass and will review them fully next pass. mascot-animal doesn't touch this lane. main changed only catalog.py and the create_event UTC offset. Open findings are unchanged: planner-28, planner-24, planner-29, planner-6 (P1); planner-26, planner-27, planner-25 (P2).

## Pass 40 notes

Pass 40: no new findings. brain-8 is merged into main, and 9a47376 tightens the permission gate (a matching phrase only counts when the window has an Allow/Deny-style button); no issues. planner-demos gate.py decontaminates synthetic states against the v2-holdout goals, the v1 tune/holdout/holdout2 goals, live_t1 and evals/external (exact, 13-gram, edit<=1) and rejects equal goal+observation pairs; no leakage found. Open findings on main are unchanged: planner-28 (compose_text, no sendgate), planner-24 (orchestrator.py L1263), planner-29 (validator has no few-shot check), planner-6, planner-26, planner-27, planner-25.

## Pass 39 notes

Pass 39: no new findings. planner-29 is now on main (the v2 bench merged without a few-shot overlap check). brain-8 adds a permission-prompt gate: it never answers system permission dialogs, asks the user instead and resumes afterwards. It also adds absolute folder paths and web question answers. I found no issues in a static review. planner-demos uses Anthropic and OpenAI teachers; it doesn't import the planner_v2 or holdout scenarios, so I found no eval leakage. main's HandsKit comms RPCs and the relative-path refusal look fine. Open findings: planner-28, planner-24, planner-6, planner-29 (P1); planner-26, planner-27, planner-25 (P2).

## Pass 38 notes

Pass 38: no new findings. main merged comms (reviewed in passes 35-36) and app-ui. wip adds HandsKit Contacts.swift and MessagesCompose.swift: the body is set through AX rather than keystrokes, and send re-checks the frontmost window and draft before posting one Return. No issues. Open findings on main are unchanged: planner-28 compose_text L70 (wip's own comment confirms that Return sends in Messages), planner-24 L1111, planner-26 L293, planner-27 L1763, planner-25 planner.py L339, planner-6. planner-29 is still on data-planner.

## Pass 37 notes

Pass 37: no lane changes. main merged bench-fix (harness fixes) and added live-suite preconditions and final-state checks, outside this lane. Open findings on main are unchanged (line numbers moved): planner-24 orchestrator.py L1074, planner-26 L293, planner-27 L1704, planner-28 compose_text.py L70, planner-25 planner.py L339, planner-6. planner-29 is still on data-planner.

## Pass 36 notes

Pass 36: 1 new P1 (planner-29: planner bench v2 goals near-duplicate the few-shot examples the runner puts in the prompt, and the validator doesn't check against the few-shot file). comms c94a407 is a merge of main plus a fix to the fake planner worker in tests; the send confirms are unchanged. bench-fix only brings in main's brain-7 files plus harness fixes. app-ui, decisions and data-route don't touch the planner lane. Open findings on main are unchanged: planner-28 compose_text L70, planner-24 L984, planner-6, planner-26, planner-27, planner-25.

## Pass 35 notes

Pass 35: no new findings. brain-7 (#25), report (#22) and native-research (#23) are merged, so planner-28 is now on main. cloud/comms: messages_send and the draft_email send are both behind ask_confirm, with an excerpt and the recipient in the summary; a confirm timeout counts as no. Before sending, it re-checks that the draft window is still frontmost. The Mail send combo is cmd+shift+d and Gmail's is cmd+return. No issues found in a static review. Open findings on main are unchanged: planner-24 L984, planner-26 L289, planner-27 L1516, planner-25, planner-6.

## Pass 34 notes

Pass 34: 1 new P1 (planner-28: compose_text types generated multi-line text into the focused field with no sendgate or confirm). brain-7 also adds: a sign-in gate that blocks typing values the user never said into email/password fields (good, matches rule 16); a login-page hint for the planner; a spoken site-name to URL table; and set_escalation, which loads or unloads the 35B planner with a 48 GB and memory_level>=40 guard (matches AGENTS). app-ui adds config frames that are acked via server tasks; no issues. native-research, report, decisions and data-pipeline don't touch this lane. Open findings on main are unchanged.

## Pass 33 notes

Pass 33: no lane changes; main only added briefs, and decisions e125c13 doesn't touch this lane. I re-checked the open findings on main and none has changed: planner-24 L984, planner-26 L289, planner-27 L1516, planner-25 planner.py L334, planner-6. Note for the comms-builder brief: send confirmations for contacts-first messaging and email drafting already go through sendgate.py (planner-lane safety). Keep any new messaging skills behind that gate.

## Pass 32 notes

Pass 32: no lane changes; main only touched AGENTS.md. I re-checked the open findings on main and none has changed: planner-24 L984, planner-26 L289, planner-27 L1516, planner-25 planner.py L334, planner-6.

## Pass 31 notes

Pass 31: no new findings. brain-6 (#21) is merged, so planner-27 is now on main (L1516). 82d94d9 adds Zen, Vivaldi, Opera and Orion to the browsers whose chat and mail tabs get send confirmations, with tests; no issues. Open findings on main are otherwise unchanged (planner-24 L984, planner-26 L289, planner-25 planner.py L334, planner-6).

## Pass 30 notes

Pass 30: 1 new P2 (planner-27). brain-6 adds sendgate.py: Enter and send confirms now cover chat and mail apps and browser tabs for them, not just Mail, Messages and Slack. It also adds a safety gate on grounded clicks (target label, composer or payment context, the AX label under the point, otherwise OCR, failing closed). It looks correct; 126 focused tests pass. Open findings on main are unchanged (planner-24 L977, planner-26 L289, planner-25 planner.py L334, planner-6).

## Pass 29 notes

Pass 29: no lane changes; main only merged pitch-4 (docs) and the spend-guard fix. I re-checked the open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 28 notes

Pass 28: no lane changes; main only touched AGENTS.md (competitor benchmark overlap rule), and pitch-4 and data-pipeline don't touch this lane. I re-checked the open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 27 notes

Pass 27: no lane changes; main only touched AGENTS.md and the serve_brain router default. I re-checked all open findings on main: planner-24 (orchestrator.py L977), planner-26 (L289) and planner-25 (planner.py L334) are unchanged, and planner-6 is unchanged.

## Pass 26 notes

Pass 26: no new findings. grounder-wire (#19) and pitch-3 (#18) are merged. The prompt now lists click "<description>" below skills, keyboard shortcuts and pressing elements, and rules 16-18 are in planner_fewshot.md. planner-26 is now on main. Calculator is at L977.

## Pass 25 notes

Pass 25: 1 new P2 (planner-26). main: holdout-2 (12 scenarios) was correctly written after holdout-1 was used to derive rules 16-18, so treat holdout-1 as tuning data from now on, and the bench now passes few_shot=None. grounder-wire: the `click "<target>"` DSL goes through a fresh screenshot and the grounder, with a confirm for dangerous labels and screenshots deleted afterwards; the DSL parse and serialize round-trip is consistent.

## Pass 24 notes

Pass 24: no new findings, and the open findings are unchanged.

Resolved: planner-23 on main (the volume fast path was dropped in the merge). 89 tests pass on main, including the planner-20 repro.

## Open P1 (ranked)
1. planner-24 P1 (main, new via PR #16) — calculator digits are sent as raw global `keys` after an unverified `open Calculator`, so they can land in the user's frontmost document — ml/src/brain/orchestrator.py L954-957
2. planner-6 P1 (main) — Premiere is still keyboard shortcuts only, with the 8766 bridge not connected — app/Sources/HandsKit/Skills.swift

## Highest-leverage next moves
- orchestrator._deliver_calc: replace the raw `keys` acts with `skill type_text text="<expr>="` (Calculator is a keystroke_app on main, so the target is checked and not_frontmost returned).
- planner.py: build OpConstraint at warmup (planner-25, P2).
- Copy reviews/planner/tests/test_planner20_done_reject_streak.py into ml/tests as a regression test.
- Premiere: add an expect to each premiere_command, or connect the bridge.
