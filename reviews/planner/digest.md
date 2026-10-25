# Planner review digest — pass 98

Heads: main b00f679 (unchanged), wip/local 73f8136 (Premiere focus guard, value diffs, ui_only fresh observe).
Open: 0 P0, 21 P1, 16 P2. New: 0. Resolved: 0.

## Reviewed, no issue
- wip repeated-Shift+3 guard: a second `keys shift+3` in the same Premiere window with no action in between returns a failed action with guidance. It stops the batch and counts as a normal failure, so it feeds the loop guard. Reset by any other action, a window change, a failed send or a new task; 7 tests.
- wip obsdiff.render_line now emits value= for slider/stepper/incrementor/picker and HotText/clipSpeed buttons; matches Swift Serializer.line on the same branch, so diff-rebuilt observations still equal a fresh observe.
- wip ui_only planners skip diff chaining and observe fresh each turn: one extra observe per turn, opt-in path only.
- Premiere hint now says focus may not show in AX. "Reopen Speed/Duration to verify" is still a prompt instruction only; planner-64 stays open.

## Top open
- planner-67 (P1, main): failed expect on an AXLoaded page re-polls verify up to 15 s; early exit reads a String as a dict. wip loop is correct; port it.
- planner-66 (P1, wip): finance numbers aren't read back from the sheet.
- planner-64 (P1): Premiere marker/cut/export have no harness end-state or export-file check.
- planner-59 (P1): failed soft expect doesn't stop the batch or count toward the loop guard.
- planner-63 (P1): destructive-refusal regex refuses "show all files in Downloads".

## Decisions for lead
1. Port wip's page-load loop to main (planner-67) before the demo.
2. Add read-back checks for finance and Premiere.
