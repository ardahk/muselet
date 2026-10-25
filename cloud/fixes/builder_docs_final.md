# Lane: docs-final (pitch, demo script, report) — fast
Read `cloud/builder_common.md`, `AGENTS.md`, `tools/serve_brain.sh` header, `docs/REPORT.md`, `pitch/*.md`. Branch
`cloud/docs-final` off latest main, one PR within 60 min (the lead merges without review; demo freeze 06:00 PDT Sun).

Update `docs/REPORT.md`, `pitch/demo_script.md`, `pitch/claims.md`, `pitch/devpost.md`, `pitch/architecture.md`,
`AGENTS.md` "Current serving configuration" to match what ships tonight (read the code, don't guess):
- System 1: it3 router (catalog v3, tau .50) for OS-level skills only (`kind: system` in skills/catalog.json).
- Agentic apps (`AGENTIC_APPS=1`, default): app tasks (Clock timers, Reminders, Notes, Calendar, Messages, Gmail/Mail
  replies, Music, Premiere) are operated by the planner over Accessibility: observe -> act -> verify, with a
  rule-based "Finish when" criterion (ml/src/brain/finish.py) and programmatic evidence that ends the task as soon as
  the goal is visible (Pause button for media, cart count +1, Clock live row, ...).
- Planners: fine-tuned LoRA 4B for normal multi-step tasks (holdout mean .850, ~0.3 s/step); Qwen3.6-35B-A3B (MoE,
  ~3B active, think 512) for agentic-app / browser / open-ended / blind tasks (`BLIND_PLANNER=escalate`, default when
  cached; base/planner selectable); offline planner numbers already in REPORT stay as they are.
- Browser: same tab within a task, the site's own search box (hand-built search URLs rejected), default browser from
  LaunchServices, page-load waits.
- Safety: confirm before send/delete/buy/post; grounded (pixel) clicks blocked in apps holding user data after a real
  incident (a Spotify playlist was removed from the user's library by a mis-grounded click; disclose briefly and
  honestly in REPORT under "Incidents and fixes"); planner AppleScript UI scripting needs confirmation.
- Benchmarks: only numbers already recorded in REPORT/claims with sources; HobbyLM has NO valid comparable score yet
  (say so); DeskMind decision-model comparison: theirs .831/.658 vs ours .779/.622 (we're behind; say so).
`pitch/demo_script.md`: a 2-3 minute voice demo in this order, each line marked `[verified]` or `[needs live check]`
(mark all agentic ones `[needs live check]`; the lead will flip them): "volume thirty" / "dark mode" (instant, System 1);
"Play some jazz on YouTube" (search box, plays, stops on Pause); "Set a timer for two minutes" (agentic Clock);
"Remind me to call mom at 5"; "Open Notes and write a template about my day"; with a Gmail email open in Zen
"Reply to this email saying I can do Thursday at three" (draft, never sends); "Add some chicken to my cart" on Amazon
(adds once, never buys); "Erase every file in my Documents folder" (refuses). Keep the on-device story front and centre.
