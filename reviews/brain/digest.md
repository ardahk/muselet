# brain lane digest — pass 27 (2026-10-24T12:10Z)

Pass 27: main d7c192f (serve_brain default router it2, tau .65, it2 as its own ARGS; AGENTS.md serving config) and wip/local 367d450
(= main); no ml/, evals/ or prompts/ changes since 04c3930, so every pass-26 result below stands. cloud/data-pipeline 0ce9ea6:
evalcheck reports only (outside lane). Router-number contamination concern closed: AGENTS/serve_brain now quote route_v1_clean
(103), and route_v1_clean.jsonl is byte-identical to route_v1_clean_both.jsonl (clean vs both main-final and it2 training data),
so it2's .913 is a clean number. Minor: serve_brain.sh ARGS comment still says "the router itself when it is r2 ... base otherwise",
but the code (correctly per AGENTS) uses it2 as its own ARGS.

## Pass 26 (2026-10-24T11:55Z; covers PULSEs 11:34Z and 11:49Z)

Reviewed: main 7147694 -> 04c3930 (generic_decide init fix f5b54bd; merged cloud/grounder-wire #19: `click "<target>"` DSL ->
screenshot -> Grounder -> act click, blind-observation hint, lazy --grounder-* flags, default eyes-4b; planner prompt rules 16-18
and click "<description>"; evals/route_v1_clean_both.jsonl 103), wip/local aec8fbf (= main), cloud/grounder-wire afb12a6,
cloud/data-pipeline 9b36081 (training report; outside lane), cloud/pitch-3 e203181 (pitch only).
Tests: main 04c3930 1133 passed / 2 skipped / 1 deselected (`-k "not real_model"`: test_alphabet_and_prefix_real_model
runs for minutes on Linux CPU; environment, not product).

Open: P0 0, P1 5, P2 6.  Resolved this pass: brain-26 on main (separate `_init_done` queue, generic_decide.py:135-159).

## Open P1 (ranked)
1. brain-25 calculator delivery: `act open Calculator` has no expect; keys go to whatever app is frontmost. test_brain_pass24.py.
2. brain-24 fuzzy path lookup: "trash invoice 2024" -> invoice 2023.pdf.
3. brain-16 abs_level: '3 pm' -> 3, 'volume 20%' after 'turn up' -> 20, 'for a min' -> 0, 'battery is full' -> 100.
4. brain-22 planner history `x -> ok` vs `[ok] x` few-shot; `press #4 -> ok` parses as an action.
5. brain-17 compound check runs serial route passes before speculative reuse.

## New P2
- brain-27 grounded click danger check reads only the planner's description (orchestrator.py:1332): `click "the paper plane icon
  next to the message"` clicks with no confirm. test_brain_pass26.py.

## Notes (no finding)
- grounder-wire: screenshots deleted after locate; `expect` verified via _rpc_action; `click "x" -> ok at 1,2` history lines are
  rejected by dsl.parse (bad modifier), so brain-22 does not extend to grounded clicks.
- Grounder model calls go through the single MLX worker, so a grounded click as action 1 waits for the rest of the planner batch
  to finish decoding (inherent to one-GPU-thread; worth ending the batch after a grounded click).
- First grounded click loads eyes-4b (mlx-4bit) lazily mid-task; pre-warm before demo segments that use it.

## Next moves
1. Gate calculator keys on `expect app "Calculator"` before the demo (brain-25).
2. Exact-only path matches for trash/move; fuzzy -> ASK (brain-24).
3. Anchor abs_level markers to the property; reject times/durations (brain-16).
4. dsl.action_line: reject `-> ok|failed` suffixes (brain-22).
5. OCR/AX-hit-test the grounded point before clicking dangerous-looking targets (brain-27).
