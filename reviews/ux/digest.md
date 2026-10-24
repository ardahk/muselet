# ux digest — pass 43

Heads: main 2a2c2a9 (briefs only: ui-polish, planner-lora), wip/local 4f963a7 (same as main for lane files), w9-safety 50a3b25, memory 4b519b1.

Counts: 0 P0, 0 P1, 10 P2. One new: ux-24.
Open P2, ranked:
- ux-14: a declined or timed-out confirm leaves the mascot thinking (orchestrator.py)
- ux-19: a grounded-click confirm timeout says 'Something went wrong' (orchestrator.py:1829, 1887)
- ux-24 (w9-safety): any '[' or backslash forces a confirm on read-only scripts (orchestrator.py _SCRIPT_BLOCK)
- ux-17: the Calculator answer is shown last (orchestrator.py)
- ux-20: the first grounded click cold-loads eyes-4b with no visible feedback
- ux-16, ux-18, plus rechecks ux-12, ux-15, ux-22

Highest-leverage next moves:
1. ux-14: ui('idle') after every 'Okay, cancelled', and reset the mood in onConfirmCancel (~0.25 h)
2. ux-24: before merging w9-safety, narrow the '[' and '\\' blocks and add must-not-confirm read fixtures (~0.5 h)
3. ux-19: guard the two grounded-click ask_confirm calls (~0.1 h)
4. ui-polish brief: the 1 s pill dwell slows click-to-talk discovery for judges; keep the 'Hold right ⌥' hint on the first poke (already the case)
