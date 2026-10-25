# Lane: open-ended — do sensible things it was never trained on ("play me some jazz on Spotify")

User: "make our agent smart enough to do things it is not trained on". Branch `cloud/open-ended`, PR, Python.
1. Write `evals/open_ended.jsonl`: 25 live acceptance tasks in apps/sites without a dedicated skill, each with a
   screen/file-checked end state: play jazz on Spotify (app), play a song on YouTube in Zen, add an item to the Amazon
   cart (same tab, never buy), directions to SFO in Maps, set Slack status, add a Reminder with a due date, change
   wallpaper, create a calendar event from an email on screen, find a file and rename it, etc. No sends/purchases.
2. Make the planner good at them: (a) app-knowledge hints retrieved per goal (URL schemes like spotify:search:,
   app search shortcuts cmd+F / cmd+L, "/" on YouTube, AppleScript dictionaries only for read/play verbs), (b) a
   search-then-act pattern (search field -> results -> press the best match -> verify playing/added), (c) give the
   planner the screen context (coordinate with the fallback lane, which adds context + tool-failure handoff).
3. Measure on the Mac (lead runs it; put the exact command under `## Mac requests`): pass rate and step latency,
   before/after.
