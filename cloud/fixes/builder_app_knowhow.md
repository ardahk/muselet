# Lane: app-knowhow (fast; speed over tests)
Read `cloud/builder_common.md`, `AGENTS.md`. Branch `cloud/app-knowhow` off latest main (after PR #91 agentic-apps lands;
rebase if needed), one PR, open within 45 min. Prompts + small Python only. Targeted tests + one full `ml/tests` pass.

Apps are now operated by the planner (AGENTIC_APPS default on; `ml/src/brain/agentic.py` builds the hint, `finish.py`
the finish criterion). A one-line hint isn't enough: in a live test the planner pressed Clock's duration wheels instead of
Pause. Give the planner concise, correct app know-how in `prompts/app_hints.jsonl` (existing format: id, match, skills,
tips; `ml/src/brain/app_hints.py` selects them by goal words and app name — make sure the agentic route's goal/hint text
and the observed app name trigger the right entry; add `match` words like "timer", "remind", "note", "event", "text",
"reply"). Tips must be facts about macOS 27 apps; prefer keyboard shortcuts and labelled AX controls; 2-5 tips each, short:
- Clock (timer): Timers tab (radio/tab "Timers"); duration wheels hr/min/sec: press a wheel then type digits; button
  "Start"; running timer row has "Pause"/"Resume" and the detail pane has "Cancel"; pause = press "Pause" ONCE then done.
- Reminders: cmd+n new reminder in the selected list, type the title, return; a time: use the "i" info / date field.
- Notes: cmd+n new note, type into the note body (textarea), first line becomes the title.
- Calendar: cmd+n new event, type "Title tomorrow at 3pm" natural-language quick event, return.
- Messages: cmd+n new message, type recipient in "To:" field and return, type body in the message field, then `confirm`
  before pressing return (never send without confirm).
- Mail / Gmail web: reply = press "Reply" on the open message, type into the reply body, never press Send without confirm.
- Maps: type destination into the search field, return, press "Directions"; done when a route with a duration shows.
- Premiere Pro (blind canvas, keyboard first): cmd+i import, cmd+k add edit at playhead, cmd+d default video transition,
  cmd+r speed/duration dialog, m add marker, cmd+m export.
Also remove any tip that encourages grounded/pixel clicks in apps with user data (Spotify, Music, Photos, Mail, Messages,
Notes, Calendar, Reminders, Contacts, Finder, System Settings). Tests: hint selection for each new entry.
