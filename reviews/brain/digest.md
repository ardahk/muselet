# Brain lane digest — pass 34 (2026-10-24T16:45Z)

main c949565 / wip/local 4ec066f unchanged. New: cloud/brain-7 13432fe (first-use fixes: site/browser rewrites,
sign-in gate, compose_text, on-demand 35B escalation, no-op press guard), cloud/app-ui afb2688 (config frame + Swift UI).
brain-7 suite: 1222 passed, 2 skipped, 1 deselected (Linux-slow real-model test).

Open: P0 0 | P1 7 | P2 8

## P1
1. brain-25 — Calculator delivery can type into the wrong frontmost app (main).
2. brain-24 — "trash invoice 2024" picks invoice 2023.pdf (main).
3. brain-29 (new, brain-7) — installed Zoom/Teams/Outlook open their websites; one failed `apps` RPC makes every
   site-named app (Slack, Spotify, Notion...) open its website for 60 s. tests/test_brain_pass34.py.
4. brain-30 (new, brain-7) — 35B escalation: two overlapping enables load two ~20 GB copies; "off" during a load leaves
   it resident. tests/test_brain_pass34.py.
5. brain-16 — abs_level misreads "3 pm", "20%", "for a min", "battery is full" (main).
6. brain-22 — planner history `x -> ok` vs few-shot `[ok] x` (main).
7. brain-17 — compound check serial route passes (main).

## P2
- brain-31 (new) — brain-7 and app-ui config_ack schemas disagree (no `ok` field) -> Settings shows "Not available"
  after a successful load; cli.py/server.py conflict.
- brain-27, brain-28 (sendgate gaps), plus older P2s unchanged.

## No findings
- Sign-in gate (typed text must appear in goal/answers), no-op press guard (3 identical empty-diff presses fail),
  compose_text (150-word cap, verify note appears), hidden `router:false` skills leave the route question unchanged.
- cloud/data-pipeline 6c1e565, cloud/decisions 184c80f, native-research, report: outside the lane.

## Lead decision
- brain-7 vs app-ui: on-demand 35B load (brain-7) or resident-only toggle (app-ui, matches the memory budget).
  Pick one design and one ack schema before merging either.
