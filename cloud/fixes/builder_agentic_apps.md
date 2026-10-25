# Lane: agentic-apps — apps are operated by the planner, not hand-coded skills

Read `cloud/builder_common.md` and `AGENTS.md` first. Branch `cloud/agentic-apps` off latest main, one PR, Python
(+ `skills/catalog.json`). Open the PR within ~90 min; push hourly. Another lane (`cloud/agentic-loop`) is editing
done-verification / page-load / workflow memory in `orchestrator.py`: stay out of those functions; rebase often.

## User decision (Sat night)
"I don't like the skill approach that much, maybe for some macOS functions sure, but for apps and stuff we should be
agentic, not coding. We are using AI here for a reason." Skills stay only for OS-level functions; anything that
operates an app's UI goes through the planner (observe -> act -> verify), driven by AX (screenshots only for blind
apps). Keep the old behaviour selectable (standing rule: never delete an option before the user reviews it).

## Implement
1. **Catalog kind.** Add `"kind": "system"|"app"` to every skill in `skills/catalog.json`.
   - system (keep as skills): set_volume, change_volume, mute, set_brightness, dark_mode, wifi, bluetooth,
     lock_screen, sleep_display, battery_status, take_screenshot, open_app, quit_app, hide_app, window_layout,
     open_url, web_search, open_folder, open_file, find_file, new_folder, move_to_trash, empty_trash, type_text,
     copy_selection, media_control.
   - app (agentic): start_timer, create_event, create_reminder, new_note, compose_text, play_music, todays_agenda,
     send_message, compose_email, draft_email, premiere_command, premiere_edit.
   - finance_review, advisor_prep: `kind: "analysis"` (local LLM analysis tools over files; unchanged).
   Swift reads catalog.json: make sure an extra key doesn't break its decoder (check `app/Sources` catalog decoding;
   if it's strict, note it under `## Mac requests`).
2. **Flag** `--agentic-apps on|off` (default on) on `brain serve`, env `AGENTIC_APPS` in `tools/serve_brain.sh`
   (default 1). Off = today's behaviour exactly.
3. **Routing (on).** Wherever a skill of kind `app` would execute — router top-1 in `_engine_route`, the
   deterministic pre-routes in `handle_utterance` (comms `parse_message` redirect, `compose_text.parse_request`,
   `draft_email.parse_request`, `premiere_edit.parse_request`, calendar/reminder parsers), slot-filling, memory
   follow-ups that replay an app skill, compound steps — call `_planner_loop(text, trace, hint=...)` instead.
   The hint carries the router's extracted args as plain facts, e.g. `start_timer duration="10 minutes"` ->
   `hint="use the Clock app's Timers tab; duration 10 minutes"`, `send_message to="Caleb" body="..."` ->
   `hint="use the Messages app; recipient Caleb; message: ..."`. Use the normal planner selection (LoRA, or base
   when blind/open-ended), not forced blind. Trace `{"agentic_app": {"skill": ..., "args": ...}}`.
4. **Planner can't shortcut it.** With agentic apps on, app-kind skills are removed from the planner's visible
   skill list and a planner `skill <app-kind>` line is rejected with `skill disabled: operate the app's UI` (no loop
   strike). System skills stay available to the planner (open_app, type_text, open_url, ...).
5. **Finish criteria** (`ml/src/brain/finish.py`): timer -> "Clock shows a running countdown of about <N>";
   event -> "the event <title> appears in Calendar on <date>"; reminder -> "the reminder <text> appears in
   Reminders"; note/compose -> "a new note containing <topic> is open"; message -> "the message to <recipient> is
   typed in Messages and you have asked to confirm sending"; email draft/reply -> "a draft reply with the text is
   visible in the reply box (not sent)"; play_music -> existing play criterion; agenda -> "today's events are read
   back from Calendar". Pass the args through so the criterion names concrete values.
6. **Safety is unchanged and must be tested:** sending (Messages/Mail/Gmail send buttons, Return in a message
   composer), deleting, buying, posting still require the existing `confirm` gates in the executor
   (`_skill_risk`, the composer-click confirm, script confirm policy). Add tests proving an agentic message flow
   cannot send without a confirm, and that the planner's confirm summary names the recipient.
7. **Tests:** routing per app skill in both modes (fake planner), planner skill-list filtering, the rejection,
   finish criteria strings, and flag off == old behaviour (existing tests must pass unchanged with
   `agentic_apps=False`; set that in the test fakes where they assert skill routing, and add new on-mode tests).
   Gates: full `uv run --project ml pytest ml/tests -q` + `bench/tests`.

PR body: `## Handoff`, per-item summary, test summary, `## Mac requests` (live checks for the lead: "Set a timer for
ten minutes", "Remind me to call mom at 5", "Create an event tomorrow at 3 called demo", "Write a note about my
day", "Text Caleb that I'll be there in ten" (answer no), "Reply to this email saying ..." with a Gmail email open).
Don't merge; the lead reviews and merges.
