# evals-safety digest — pass 36 (2026-10-24T16:33:37Z, main@c949565)

Open: P0 0, P1 3, P2 9.

## Open P0/P1 (ranked)
1. **-33 (P1, new; cloud/brain-7 13432fe vs cloud/app-ui afb2688, both unmerged):** conflicting `config`/`config_ack` contracts. app-ui's Swift reads `ok`, which brain-7 never sends, so every ack reads as a failure. brain-7 loads 35B on demand and app-ui only toggles a resident one. server.py conflicts on merge.
2. **-25 (P1, main):** the document guard skips 9/43 live cases, and skips leave the denominator.
3. **-11 (P1, main):** `done` is accepted with no harness goal/result check.

## Next moves
1. Settle one config/config_ack contract (with `ok` plus the actual state) before brain-7 or app-ui merges (-33).
2. Before the morning live runs: count skips in the live pass rate, or narrow the document guard to each case's apps (-25).
3. REPORT.md:122 and claims.md:66: add the 12/43 trace-graded caveat (-24).
4. Report the planner on holdout-2 with the prompt SHA (-31).

## Checked, nothing material (pass 36)
- data-pipeline 6c1e565: route_v2 is frozen (955 items, 0 overlap with the training pools and other evals), and evalcheck now includes route_v2, so the it3 training gate covers it.
- decisions 184c80f/43abfa3: the trainer has an estimate-based preflight, --max-usd and a $25 acknowledgement gate. The Tinker backend still has no runtime cap (-28 unchanged).
- brain-7: sign-in gate on typing, site/browser URL rewriting, compose_text verifies the note appears, no-op press guard. Confirm gates unchanged.
- native-research, report: docs only (see -24 for the report).
