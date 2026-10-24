# brain digest — pass 1 (2026-10-24T05:25Z, wip/local bcd3b75)

Open P0/P1 (ranked):
1. brain-6 P1 MLX forward passes run on the event loop, blocking receive loop — ml/src/brain/orchestrator.py
2. brain-3 P1 parse_duration returns wrong seconds for compound spoken numbers — ml/src/brain/decision.py
3. brain-4 P1 parse_datetime silently returns wrong dates and times — ml/src/brain/decision.py
4. brain-5 P1 37th route option crashes: renderer ignores filtered usable_ids — ml/src/brain/decision.py
5. brain-7 P1 Route context is constant (app/focused/last_action never populated) — ml/src/brain/orchestrator.py

Resolved this pass: brain-1 (P0 route render parity, now 50/50 vs artifact), brain-2 (args signature).

Note: wip/local bcd3b75 decision.py:389 is a SyntaxError (mid-edit `for _s in ("`), so the brain does not import at that snapshot; re-check next pulse.
Not verified: hybrid DeltaNet cache deepcopy exactness on real logits (CPU run too slow here).

Highest-leverage next moves:
- `self.IDS = keep` in AlphaChoiceRenderer (one line; unblocks catalog growth/shortlist).
- Wrap engine.route/args in a 1-worker executor.
- Replace number/date parsing with a small rule parser that returns None on doubt.
- Plumb utterance ctx + last_action end to end.
- Make test_brain_pass1.py's parity check against route_render_samples.jsonl a real ml/tests test.
