# Cloud builder: brain-5, live-suite fixes (argument semantics + compound follow-ups) — Muselet

Repo `ardahk/muselet`. Read `AGENTS.md` first ("Model picks, code parses"; Standing decisions). Branch `cloud/brain-5` from
main, one PR. Another builder is changing `planner.py`, the orchestrator's planner batch log and `cli.py` flags on
`cloud/brain-4`. Stay out of those areas so both PRs merge cleanly. Your area is the routed-skill path:
argument coercion, slot filling, compound handling and path resolution in `ml/src/brain/orchestrator.py` (plus small
helpers in new modules). Linux has no Metal: test with fakes. No prompts/ or evals/ edits.

Evidence: tonight's live suite on the Mac (`bench/live/run_live.py`, real final-state checks). The lead read the traces;
the trailing-comma path bug is ALREADY fixed (the trace shows `parent="~/Desktop"`). Don't redo it. Fix these:

1. **Vague quantities dead-end in a question.** "turn it down a little" and "make it way louder" route to
   change_volume (p .99), but ARGS returns `missing=delta`, so Muselet asks "how much?". Fill by code when delta is missing
   and the utterance has a direction word:
   - up / louder / raise / increase / higher, or down / quieter / softer / lower / decrease / turn down;
   - plus a degree word: a little / a bit / slightly / a touch / a notch = 10; a lot / way / much / really / a ton = 30;
     no degree word = 10.
   - Same for brightness with direction words (brighter / dimmer / darker screen). Send `skill set_brightness delta=±N`;
     HandsKit adds `delta` tonight.
   - Absolute phrases ("all the way up", "max", "to 30") stay absolute: set_volume / set_brightness level.
2. **On/off polarity from words.** "silence the speakers" extracted mute on=false, and "go back to light mode" extracted
   `missing=on`. Add a small lexicon applied by code when it hits unambiguously; it overrides the model's bool, and is
   ignored when hits conflict:
   - mute: silence / hush / quiet the sound / mute → true; unmute / sound back on → false.
   - dark_mode: light mode / light theme / turn off dark / disable dark → false; dark mode / dark theme / night mode → true.
   - wifi / bluetooth: on / enable / turn on / connect → true; off / disable / turn off / disconnect → false.
   Tests for each word plus negation cases ("don't mute" → don't act: ASK).
3. **"…and open it" is dropped.** "create a folder on my desktop called trip photos and open it": compound was rejected
   ("open it" routes to open_file at .685 < .75), so only new_folder ran.
   - (a) In the compound path, a clause matching `^(and |then |and then )?(open|show|reveal) (it|that|them|the folder|the file)$`
     after a creating skill is a follow-up resolved by code:
     - after new_folder → open_folder path=<parent>/<name> from the previous clause's coerced args;
     - after take_screenshot → open_file with the screenshot path from the skill result;
     - after new_note → no extra action (Notes shows it).
   - (b) Otherwise, if compound is rejected and any later clause starts with an imperative verb (open, show, close, play,
     turn, set, make, create, send, search, find, take, start, put, add, move, delete, go, switch, mute, unmute, lock,
     empty, quit, hide, copy, paste, type, write, email, text, call, schedule, remind), don't execute only the first
     skill. Send the whole utterance to the planner (MULTI_STEP, hint = whole-utterance top label).
   - Keep today's behavior for "search for salt and pepper" (same-skill 'and') and "text mom I love you and miss you"
     ("miss" isn't in the verb list).
   - Trace `compound_followup` / `compound_to_planner`.
4. **Wrong file trashed (caught by confirm).** "move muselet trash probe to the trash" extracted
   `path="muselet invoices"`. For path args of move_to_trash and open_file (and open_folder when the value isn't a known
   folder alias):
   - If the ARGS path doesn't exist, resolve by code from the utterance's object phrase. Fuzzy-match file and folder
     names (normalize case, spaces/dashes/underscores, drop extensions) in ~/Desktop, ~/Documents, ~/Downloads, depth ≤ 2,
     max 2,000 entries, ≤ 150 ms.
   - Exactly one strong match → use it. Several → ASK naming up to 3 candidates. None → ASK.
   - The move_to_trash confirm summary must show the resolved full path. Tests with a temp HOME.
5. **"open my downloads as a list" ignores the view.**
   - If the utterance mentions as a list / list view / as icons / icon view / columns / column view / gallery, pass
     `view=list|icons|columns|gallery` to open_folder. HandsKit adds the arg tonight.
   - If the skill result is an unknown-arg error, follow up with `act keys cmd+2` (list) / `cmd+1` (icons) /
     `cmd+3` (columns) / `cmd+4` (gallery).
   - Tests.
Reply with the PR link, the test count, and anything in the traces you think the lead misread.
