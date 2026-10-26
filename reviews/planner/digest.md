# Planner review digest — pass 101

Heads: main 32c0ad4 (unchanged), wip/local d714345 (+ fixture server, training tasks/graders, harness milestones/confirm gate/n_actions, LH-v1 checks that never launch apps).
Open: 0 P0, 25 P1, 14 P2. New: planner-71 (P2). Updated: planner-69. Resolved: none.

## New / updated
- planner-69 (P1, update): wiki graders unchanged, and the training spec grader copies the same pattern (t3/t5 "not" lists, digits-only years). The H7 trajectory filter keeps only bare-answer runs, which inflates the LoRA's measured wiki gain.
- planner-71 (P2): training tasks share pages, mailbox and templates with LH-v1 mart/mail (most-expensive vs cheapest beans, the checkout template, Priya's emails). Report those families as in-domain; only forms/bank/native/online measure transfer.

## Reviewed, no issue
- Fixture server binds 127.0.0.1 by default; /api/reset is POST-only; grader exceptions return FAIL.
- Strict pass now requires confirm_count >= 1 for require_confirm cases (checkout, reply, compose).
- Checks use a separate `is running` probe before talking to TextEdit/Numbers, so they no longer launch apps or restore user documents. This fixes a real live-safety hole.
- Setup failures are now skips with a reason, matching the AGENTS rule that a failed precondition is a SKIP; the skip reasons are reported.
- n_actions counts only act/skill RPCs from the brain.

## Still open (top)
- planner-70: THINK ignored in tools mode; 12-turn / 60 s cap.
- planner-68: deployed config unmeasured; no named profile.
- planner-66 / 64: no finance read-back or Premiere end-state check.

## Decisions for lead
1. Fix the wiki graders (eval and training) before any H1-H7 results or trajectory filtering.
2. Report LH-v1 by family; claim transfer only on held-out families.
