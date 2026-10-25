# Lane: fix-pending — a new command must never be swallowed by a pending task

User test (trace runs/traces/2026-10-24.jsonl, 20:09-20:11 PDT): "Open notes and write a template about my day" ended
`awaiting_user` (a script confirm was open). The next utterance "Text Caleb that I'll be there in ten" was fed to the
pending planner task as an answer (the planner thought "write a template ... with a message to Caleb") instead of
running the messaging flow. The same sentence with "on iMessage" worked. `_new_command_during_ask` (PR #63) only
recognises a few verbs (set/turn/open/search/...).

Fix in `ml/src/brain/orchestrator.py` (branch `cloud/fix-pending`, one PR, tests with the existing fakes):
- While a task/confirm/ask/slot is pending, treat the utterance as a NEW command when any deterministic pre-route
  matches (comms `parse_message`, `draft_email.parse_request`, sites, calculator, compound) or the router's top skill
  is confident (>= tau) and is not ASK/ANSWER; then cancel the pending item cleanly (confirm_cancel to the app, say
  nothing extra) and run the new command. Real answers ("yes", "no", "the second one", "Caleb Kawano", a bare name, a
  number, "continue") still answer the pending item.
- A pending script/action confirm that gets a new command is cancelled (never executed).
- Tests: the exact sequence above; yes/no/name answers still work; a pending messaging confirm + "turn the volume up"
  cancels the send.
