# Lane: ui-progress — the kitten must visibly keep working until the task ends (fast; merged without review)
Read `cloud/builder_common.md`, `AGENTS.md` (protocol: brain -> app `ui {mascot, bubble?, ms?}`). Branch
`cloud/ui-progress` off latest main, one PR within 45 min. Swift is uncompiled here: keep Swift changes small and in
their own commit; the lead's Mac builds it.

User: "when it is thinking, it needs to constantly show those dots so I can know that it is not done". Planner tasks now
run up to 5 minutes (35B thinks ~5-10 s per step), and the thinking indicator disappears between steps.
1. **App (Swift, app/Sources/MuseletApp/Mascot/*):** from the moment an utterance is sent until a terminal mascot state
   (success, confused, idle, sleeping) or a confirm, the kitten shows the animated thinking dots continuously, including
   while state flips between thinking and acting and while a bubble is shown. Find where the dots are drawn (search
   "thinking" in MascotView/PillView/PillController) and drive them from a single `busy` flag set on utterance send and
   cleared on terminal states/confirm/cancel; no timeouts that hide them early (keep a 6-minute safety timeout).
2. **Brain (Python):** after each planner turn, send `ui {mascot: "acting", bubble: <step>}` where <step> is a short
   (<= 8 words) human phrase for what it's doing now, derived from the batch's first action (e.g. `type #12 "jazz"` ->
   "Typing jazz", `press #40` with label "Jazz Classics..." -> "Clicking Jazz Classics", `url ...youtube...` -> "Opening
   YouTube", `open "Maps"` -> "Opening Maps", `script` -> "Checking playback"); use the element labels from the last
   observation. Never include secrets/message bodies longer than 30 chars. Unit tests for the phrase builder.
