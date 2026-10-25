# Lane: fix-apps-notes — spoken app names and "write a template in Notes"

User tests (runs/traces/2026-10-24.jsonl ~20:09 PDT), branch `cloud/fix-apps-notes`, one PR, tests with fakes:
1. "Open text edit and write hello" -> `open_app app="text edit"` -> HandsKit "app not found: text edit". Resolve spoken
   app names against the installed list (the `apps` RPC, already cached by `_app_names`) with a normalised key (case,
   spaces, punctuation, common STT splits: "text edit"->TextEdit, "face time"->FaceTime, "you tube music", "v s code"
   ->Visual Studio Code via aliases) before calling HandsKit; ask "Which app?" only when nothing matches.
2. "Open notes and write a template about my day so I can fill it out" -> compound rejected -> planner -> Notes AX tree
   empty -> the planner wrote raw AppleScript -> script confirm "Run AppleScript on Notes?" -> "Script failed". This
   is a `compose_text` job: add a deterministic pre-route for write/make/create/draft <something> (in|on|into) notes
   (and "open notes and write ...") -> `compose_text target=note topic=<...>`; compose_text must create the note through
   the native `new_note` skill (HandsKit), never model-written AppleScript, so no script confirm appears. Keep the
   planner as the fallback for anything else.
3. If the planner ever needs Notes, its AX tree was empty (window_source none) right after launch: wait for the
   window (re-observe up to 2 s) before planning blind.
