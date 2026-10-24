# Cloud builder: data-decisions (more code-verified System One decisions) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md`, `cloud/builder_decisions.md`, and the `cloud/decisions` branch
(`training/decisions/SPEC.md`, `reports/full_gen.md`). The decisions builder (session 83651a51) owns training. You
produce additional DATA and hand it over through the lead; you never start Tinker runs. Branch `cloud/data-decisions`
(new generator files only, under `training/decisions/gen_codegold/`), one PR.

Problem: only 301 code-gold states (no counting, multi-hop or long-policy) survived decontamination and teacher gating.
The JevBench hard split (temporal/numeric, multi-hop, long_policy, judge_hard, probability, trap) is where DeskMind beats
us (.676 vs .523).

1. Write programmatic generators. Each samples a realistic state (JSON or text records, tables, policies, logs,
   calendars, invoices, tickets) and typed questions (choice / noul / score), with gold computed BY CODE.
   - Families: counting/aggregation over records; multi-hop lookups across 2–3 tables; long multi-condition policies
     (2–6k tokens) evaluated by a rule engine; business-day / time-zone / leap-year date math; ≥ vs > thresholds and
     %-change bands; Bayes and base-rate probability; trap items (irrelevant salient numbers, negations).
   - Vary the wording heavily with an LLM paraphraser that never sees the gold. Shuffle options and balance the gold
     position.
2. Soft labels: follow the decisions SPEC (reasoning teacher sampled K=4, keep only when the majority equals the code
   gold), or use calibrated one-hot plus a small epsilon when the gold is certain. Document which.
3. Decontaminate against JevBench public (231), the typed-decisions test, route_v1, live_t1 and evals/external
   (13-gram + identical option sets + edit ≤ 1 for short items). Result must be 0.
4. Target: at least 2,500 code-gold states / 8,000 decisions. Deliver them as a new version of
   `jonsnov/muselet-decisions-v1` (or `-v2`), plus `training/decisions/gen_codegold/REPORT.md` with counts per family,
   a teacher agreement table and gate results.
Budget: up to $70 API total; report the spend. Reply at the halfway point with counts, then at delivery.
