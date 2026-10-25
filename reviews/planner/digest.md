# Planner review digest — pass 96

Heads: main b00f679 (README architecture image only), wip/local 35aed2d (app resolver).
Open: 0 P0, 21 P1, 16 P2. New: 0. Resolved: 0.

## Reviewed, no issue
- wip AppResolver now enumerates /Applications, /System/Applications and ~/Applications recursively (skipping package contents), so nested apps like "Adobe Premiere Pro 2026/Adobe Premiere Pro 2026.app" resolve. Exact name wins over substring; `apps` installed list uses the same walk.
- wip orchestrator app resolution: strips ".app" and a trailing year, accepts only a unique candidate, else still asks "Which app?".
- main README: image added; claims at lines 18 and 32 unchanged (planner-55).

## Top open
- planner-67 (P1, main): failed expect on an AXLoaded page re-polls verify up to 15 s; early exit reads a String as a dict. wip loop is correct; port it.
- planner-66 (P1, wip): finance numbers aren't read back from the sheet.
- planner-64 (P1): Premiere marker/cut/export have no end-state or export-file check.
- planner-59 (P1): failed soft expect doesn't stop the batch or count toward the loop guard.
- planner-63 (P1): destructive-refusal regex refuses "show all files in Downloads".

## Decisions for lead
1. Port wip's page-load loop to main (planner-67) before the demo.
2. Add read-back checks for finance and Premiere.
