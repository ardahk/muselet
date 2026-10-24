
## Your lane: `finance` — finance engine, fixtures, and the finance-track story
Files: `ml/src/brain/finance/*`, `ml/tests/test_finance.py`, `evals/fixtures/finance/*` (incl. `generate.py` and
truth files), Numbers AppleScript generation, and the planner's Numbers recipes in `prompts/planner_system.md`.
Work arrives on branch `cloud/finance` (a cloud builder) and later on `main`/`wip/local`. Read
`cloud/builder_finance.md`: it is the spec, including the lead's fixture rebalance rules.
Look hardest at:
- Money correctness: Decimal everywhere, refunds as negative spend, rounding to cents, totals that reconcile
  with the running balance. Independently recompute every truth file from the CSV with your own code.
- Rules that only work on this fixture (hardcoded rows, merchants or thresholds tuned to one statement):
  generate a second statement with a different seed and check for false positives and misses.
- Receipt matching edge cases: fuzzy merchant names, same merchant twice on a day, transposed vs other
  mismatches, date off by one (posting delay).
- AppleScript correctness for Numbers (`tell application id "com.apple.Numbers"`): string escaping, ranges,
  one call per bulk read/write, nothing that clicks cells one by one.
- Track fit: Hyphenate's judging values (works on existing systems, every action carries evidence, acts when
  confident and escalates when not). Point out what would make a judge believe it.
