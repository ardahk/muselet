# Planner review digest — pass 100

Heads: main 32c0ad4 (unchanged), wip/local 0b155b2 (+ Phase 2 long-horizon suite LH-v1: bench/fixtures seed + graders, evals/lh_v1.jsonl + builder, lab notebook, research notes).
Open: 0 P0, 25 P1, 13 P2. New: planner-69, planner-70 (both P1). Resolved: none.

## New
- planner-69 (P1, wip): the LH-v1 wiki graders fail correct sentence answers ("The Varn Spire is taller than the Oskel Tower"; "14 March 1742"), so strict pass@1 is biased by answer style. That skews the H1-H7 planner comparisons. The bank regex also matches 130.15. No fixture server is committed yet.
- planner-70 (P1, main): tools mode decodes with a hardcoded THINK_BUDGET=1024, so THINK has no effect. The non-blind planner loop is capped at 12 turns / 60 s, which binds at one action per turn (Premiere and finance demo goals).

## Reviewed, no issue
- LH-v1 safety: each case has the runner preconditions (Safari/TextEdit not running, fixture up). The sandbox is created by the runner and it refuses to reuse an existing one. Teardown is scoped to the case, and send/checkout cases require a confirm. Training wiki quizzes (t1-t5) share no entities with the eval quizzes (q1/q2). The YouTube check requires a watch URL plus "jazz".

## Still open (top)
- planner-68: deployed tools config unmeasured; not a named profile in serve_brain.sh.
- planner-66 / planner-64: no finance read-back or Premiere end-state check.
- planner-61 / planner-46: no expect on native tools; OCR every turn.
- planner-59, 58, 60, 63, 56: unchanged.

## Decisions for lead
1. Fix the wiki graders and bump the LH-v1 version before any Phase 2 result is recorded.
2. Plumb THINK into tools mode and scale the turn/time cap before running H1/H2.
