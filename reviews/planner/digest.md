# planner lane — pass 52 (main 8fb465c, wip fe6c209)

Open P0: none.

Open P1 (ranked):
- planner-45: Memory saves planner 'ok' outcomes as workflows even when done was a false accept (ml/src/brain/orchestrator.py)
- planner-44: Think ship picks qwen sampler on a one-task edge, +0.85 s p50/step (cloud/handoff/notes/planner_think_eval.md)
- planner-43: Planner LoRA dev split is random by id, so templated siblings leak (training/planner_lora/common.py on main)
- planner-42: architect-27 asks every Premiere command again, even after a planner confirm (ml/src/brain/orchestrator.py on cloud/safety-architect27)
0. planner-40: done accepted after any skill that returned ok, skipping the model check (ml/src/brain/orchestrator.py, now on main)
2. planner-31: Rule 14 'expect focused' (no ref) is rejected by HandsKit before acting (prompts/planner_system.md)
3. planner-38: Planner LoRA trained without few-shot/retrieval, but served with both by default (training/planner_lora/common.py, tools/serve_brain.sh)
4. planner-15: read-only Numbers scripts still trigger CONFIRM (ml/src/brain/orchestrator.py). Not fixed by w9.
5. planner-32: open_folder catalog lacks 'view', so demo 1 goes through the planner (skills/catalog.json)
8. planner-29: v2 bench goals near-duplicate the few-shot examples (evals/planner_v2_*)
9. planner-6: premiere_command unimplemented; catalog args mismatch the UXP bridge (app/Sources/HandsKit/Skills.swift)

Highest-leverage next moves:
- Gate memory and workflow writes on a verified done (not the skill-ok shortcut), and frame memory lines as data (planner-45, planner-40).
- THINK=512 qwen is now the serve default; switch to greedy: same accuracy within one task, -0.85 s p50 and -2.1 s p95 per step (planner-44).
- LoRA (now on main): use v2-holdout/live as the ship number, measured on the mlx4 export under the exact serve flags. Treat dev_pass 0.98 as in-distribution and don't quote it (planner-43, planner-38).
- architect-27: ask only for export (maybe the cut too), and let a planner confirm count, so demo 4 doesn't ask 3-6 times (planner-42).
- planner-verify is on main: drop the skill-ok = done-evidence rule (planner-40). Keep the decide-based verify, which also takes care of most of planner-33.
- Before any LoRA ship call, evaluate the adapter under the exact serve flags (few-shot, RETRIEVAL_K, THINK), or serve it with `--planner-fewshot none` and RETRIEVAL_K=0 (planner-38).
- W9 is merged (planner-30/24 fixed). Next, narrow `\[` to JXA computed keys and drop `\\`, `set .* to` and `format` for Numbers reads (planner-37, planner-15), or the demo-3 planner path will ask for confirmation on reads.
- brain-9: pick the browser from 'in/using X' context, not the first mention (planner-41).
- Add `view` to open_folder in catalog.json and to the prompt example (planner-32). Fix rule 14 to say `expect focused #<ref>` (planner-31).

Pass 52 notes:
- main 8fb465c: THINK=512 qwen is on by default (planner-44 is live), memory phase 1+2 and architect-27 are merged (planner-42 is on main), and the it2 tau dropped from .65 to .35 (router lane).
- Memory phase 2 writes planner successes as workflow demos and episodes (planner-45). Person memory and the denylist filter (_filter_demos) look fine. comms and typing goals are excluded from writes.
- hands-clock: the Clock AX timer lane is mostly outside this lane; no planner-path issues.

Pass 51 notes:
- main 0b83c3b merged planner-verify (#54, VERIFY_DONE on by default) and planner-28 (#66). planner-28 is resolved; planner-40 and planner-33's remainder are now on main.
- The think eval (822d7b7) ships t512 + qwen. Think clearly helps over t0: pooled 0.64 vs about 0.51 for the 4b t0 k=1 baseline. The qwen-vs-greedy choice is noise (planner-44). serve_brain still defaults to THINK=0.
- The memory and memory-lt changes since last pass are only main merges. brain-9 merged main; planner-41 is still open.

Pass 50 notes:
- main 18c139f merged brain-27 (#59), bench-28 (#60), brain-38 (#62), brain-12 (#63), brain-18 (#64), planner-think (#56), live-cases (#57) and planner-lora (#48). The lane diffs match what I reviewed on those branches in passes 46-48.
- Not merged yet: planner-verify (planner-40), safety-planner28 (planner-28 fix), safety-architect27 (planner-42).
- planner-lora export: tied embeddings are split, the trained lm_head is written, and the input embeddings equal the base (max abs err 0.013 after dequantization). split_model on main picks up an untied lm_head (decision.py:177), so serving uses the trained head.

Pass 49 notes:
- Only cloud/decisions moved (c88b613: results.md and a metrics snapshot, docs only). It changes no planner-lane files, and none of the open findings changed status.

Pass 48 notes:
- main 46b97f5 only changes the harness proxy (outside this lane). brain-9 e9e9b42 is test only; planner-41 is still open.
- safety-planner28 fb4a45a fixes planner-28 for composer targets (pending merge).
- safety-brain18 9aa2e4c: BatchCutter now counts bare catalog skill lines toward the 5-action cap, which matches what the parser counts.
- safety-brain12: a clear skill command during a pending ASK (set/open/search..., routed as a skill) cancels the ASK and runs. Fine.
- safety-architect27 Skills.swift focuses Timeline through Window > Timeline before shortcuts (uncompiled; reviewed statically, looks reasonable). Its confirm policy is planner-42.
- live-cases and brain38 (comms) are outside this lane.

Pass 47 notes:
- main a97fcba merged W9 (#46), router it3 (#52) and docs-demo-2. planner-30 and planner-24 are resolved on main. planner-37 and planner-28 are now on main.
- planner-verify d22b9a9 is a rebase plus a bank-test fix. planner-40 is still there.
- brain-9: named browser plus a hidden `browser` catalog arg (Skills.swift openInBrowser takes it; it is uncompiled). The web answer waits at most 3 s for a rich page and merges AX and OCR excerpts; page text is still framed as data. Planner warm-up runs on the serialized MLX worker; for escalate it is queued before the first escalated plan(), which costs roughly one short prefill (my estimate, not measured).
- safety-brain27 confirms grounded composer clicks when the goal shows message intent; safety-bench28 drops 3 destructive demos from retrieval. Both are fine for this lane.
- planner-think only merged main; memory/memory-lt changes are in rewrite rules, not the planner loop.

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
