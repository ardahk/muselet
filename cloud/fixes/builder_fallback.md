# Lane: fallback-intelligence — when a fixed tool can't do it, think with the screen instead of giving up

User: "if we're going to have a very dumb agent there is no point of speed; think about intelligence and the model
doing what we want." Today a deterministic tool that fails ends the request with an error bubble ("Couldn't find text
edit. Check the name?", "Couldn't open a reply in Mail", "Script failed"). Branch `cloud/fallback`, one PR, Python,
tests with fakes.
- In `orchestrator.py`, when a skill or brain tool fails for a recoverable reason (not found, not frontmost, no target,
  script failed, verification failed, missing argument the screen can supply), hand the original goal to the thinking
  planner with the fresh observation (+ OCR when AX is thin) and the failure reason as context, instead of replying
  with the error. Keep the confirm/safety gates; never retry irreversible actions blindly; cap at one handoff.
- Give the planner the live context it lacks today: frontmost app, window title, browser URL (ctx), and a compact
  "what's on screen" summary (AX text head/tail, OCR when thin) on its first turn for non-deterministic goals.
- Trace `fallback.planner: {from, reason}`. Flag `FALLBACK_PLANNER=1` default on in tools/serve_brain.sh.
