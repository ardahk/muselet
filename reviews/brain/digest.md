# brain digest — pass 2 (2026-10-24T05:45Z, wip/local 1d7cc07; main c09dcbd identical for ml/)

Open P0/P1 (ranked):
1. brain-6 P1 MLX forward passes run on the event loop, blocking receive loop — ml/src/brain/orchestrator.py
2. brain-3 P1 parse_duration returns wrong seconds for compound spoken numbers — ml/src/brain/decision.py
3. brain-4 P1 parse_datetime silently returns wrong dates and times — ml/src/brain/decision.py
4. brain-5 P1 37th route option crashes: renderer ignores filtered usable_ids — ml/src/brain/decision.py
Open P2: brain-8 last_action quoting differs from training format.

Resolved: brain-1 (route parity 50/50), brain-2 (args signature), brain-7 (ctx + last_action plumbed).
Suite at 1d7cc07: catalog 9, dsl 45, orchestrator 9, route_parity 52+1 skip pass; test_decision real-model test does not finish on Linux CPU (env, not a bug).
cloud/finance f098120 (ml/src/brain/finance/*): 90 tests pass, no findings this pass.
Not verified: hybrid DeltaNet cache deepcopy exactness on real logits.

Highest-leverage next moves:
- `self.IDS = keep` in AlphaChoiceRenderer (one line; unblocks catalog growth/shortlist).
- Wrap engine.route/args in a 1-worker executor so cancel/rpc_result flow during forwards.
- Rule-based duration/datetime parser that returns None (ASK) on doubt.
- Share one last_action formatter between training and runtime.
