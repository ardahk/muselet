# brain digest — pass 3 (2026-10-24T06:02Z, wip/local cbc4879; main dec310b same catalog v2)

Open P0/P1 (ranked):
1. brain-5 P0 Catalog v2 (41 options) crashes every route call: unfiltered ids — ml/src/brain/decision.py
2. brain-9 P0 script_needs_confirm lets click/JS/open side effects run unconfirmed — ml/src/brain/orchestrator.py
3. brain-11 P1 Planner stops before the 5th action's expect; DONE accepted unverified — ml/src/brain/planner.py
4. brain-10 P1 Bool 'on' regex override inverts mute for natural phrasings — ml/src/brain/orchestrator.py
5. brain-6 P1 engine.args still runs on the event loop, racing the MLX worker — ml/src/brain/orchestrator.py
6. brain-3 P1 parse_duration wrong seconds for compound spoken numbers — ml/src/brain/decision.py
7. brain-4 P1 parse_datetime silently returns wrong dates and times — ml/src/brain/decision.py
Open P2: brain-8 last_action quoting; brain-12 pending ASK captures next utterance.

Suite at cbc4879: test_route_parity 50 failed (brain-5); catalog/dsl/orchestrator/finance/advisor pass.

Highest-leverage next moves:
- `self.IDS = keep` in AlphaChoiceRenderer + pull the 41-option v2 artifact from cloud/data-pipeline (restores System 1).
- Make script_needs_confirm default-confirm; block click/perform action/do JavaScript/open.
- Route engine.args through worker().submit_async.
- Keep decoding expect lines after the 5th action; never accept done without a passed expect.
- Remove/narrow the bool-on override (mute first).
