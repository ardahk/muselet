# Planner review digest — pass 95 (2026-10-25T12:5xZ)

Heads: main d09f4d8 (merged #130 page-load signal + README), wip/local 01a929c (Numbers hint, AX-ref click prompt contract).
Open: 0 P0, 21 P1, 16 P2. New: planner-67 (P1). Updated: planner-65 (now on main).

## New
- planner-67 (P1, main): `_repoll_loading` caps at 15 s whenever AXLoaded is exposed and its "page loaded" early exit reads `vres["observed"]` as a dict, but HandsKit verify returns a String. So a failed expect on a loading or busy page polls verify (a full observe) every 0.1 s until it passes or 15 s pass. wip already does it right (separate observe per poll); port that and add a test. Static read only.

## Updated
- planner-65 (P2): main's `_page_loading` now counts a loaded page as loading while AXElementBusy is set; that feeds planner-67 and the one free loop-guard skip.

## Top open (unchanged)
- planner-66 (P1, wip): finance numbers aren't read back from the sheet.
- planner-64 (P1): Premiere marker/cut/export have no end-state or export-file check.
- planner-59 (P1): a failed soft expect doesn't stop the batch or count toward the loop guard.
- planner-63 (P1): destructive-refusal regex still refuses "show all files in Downloads".
- planner-58 (P1): provisional refs restart at 1 per window root.
- planner-55 (P2): README line 32 still claims .85 @ ~0.3 s and 35B only for web/blind screens; line 18 still says destructive requests are refused (planner-63).

## Reviewed, no issue
- wip Numbers hint: SORT/SORTBY spill into a separate empty destination; the native-sort guard still blocks overwriting source cells.
- wip prompt contract test for AX-ref named clicks.

## Decisions for lead
1. Fix planner-67 on main before the demo (browser steps can stall 15 s).
2. Add read-back checks for finance and Premiere.
