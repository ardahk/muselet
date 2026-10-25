# Planner review digest — pass 97

Heads: main b00f679 (unchanged), wip/local aadf777 (CANVAS_APPS prefix).
Open: 0 P0, 21 P1, 16 P2. New: 0. Resolved: 0.

## Reviewed, no issue
- wip CANVAS_APPS prefix "Adobe Premiere Pro" -> "Adobe Premiere": also covers "Adobe Premiere Pro (Beta)" and Premiere Rush/Elements, which are canvas UIs too. Test added in test_grounder_wire.py.

## Top open
- planner-67 (P1, main): failed expect on an AXLoaded page re-polls verify up to 15 s; early exit reads a String as a dict. wip loop is correct; port it.
- planner-66 (P1, wip): finance numbers aren't read back from the sheet.
- planner-64 (P1): Premiere marker/cut/export have no end-state or export-file check.
- planner-59 (P1): failed soft expect doesn't stop the batch or count toward the loop guard.
- planner-63 (P1): destructive-refusal regex refuses "show all files in Downloads".

## Decisions for lead
1. Port wip's page-load loop to main (planner-67) before the demo.
2. Add read-back checks for finance and Premiere.
