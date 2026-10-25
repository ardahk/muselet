# Planner review digest — pass 99

Heads: main 32c0ad4 (merged everything from wip: engine deletion, page-load loop, AX click refs, app resolver, Premiere focus guard, docs), wip/local 69261f5 (= main content).
Open: 0 P0, 23 P1, 13 P2. New: planner-68 (P1). Resolved: planner-67, planner-55. Promoted P2->P1: planner-61, planner-46 (both now on the deployed path).

## New
- planner-68 (P1): the demo runs a hand-written override (base 4B, native tools, THINK=1024 on every turn, one action per turn) that has no accuracy or latency numbers. The nearest measured config (base 4B, think 512, batched) was 2.6 s/step p50 with a .770 holdout mean. The override exists only as a command in AGENTS.md, so benchmarks run through serve_brain.sh measure a different config.

## Promoted
- planner-61 (P1): no expect on any native tool, so demo actions carry no expect.
- planner-46 (P1): OCR on every tools-mode turn (latency + raw screen text in the prompt).

## Resolved
- planner-67: main's load repoll now observes separately and stops when loaded.
- planner-55: docs now separate historical named-config numbers from the deployed build.

## Still open on main
- planner-66 (P1): finance numbers aren't read back from the sheet (engines now deleted on main).
- planner-64 (P1): Premiere end state / export file not checked by the harness.
- planner-59 (P1): soft expects stripped and don't stop batches or count toward the loop guard.
- planner-63 (P1): destructive-refusal regex unchanged.
- planner-60 (P1): sendgate search/find label exemption unchanged.
- planner-58 (P1): provisional refs per root unchanged.

## Decisions for lead
1. Measure the deployed tools config against LoRA DSL (pass rate + step p50) before the demo; try THINK 512/256; put the profile in serve_brain.sh.
2. Add an optional expect to native tools, and read-back checks for finance and Premiere.
