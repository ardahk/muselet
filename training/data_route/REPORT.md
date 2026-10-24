# data-route: it3 router + ARGS pool (`jonsnov/muselet-route-datums-it3cand`)

Base: `jonsnov/muselet-route-datums-it2b@8df540b` (40388 route rows). Output: **41756 route rows**
({'train': 40465, 'val': 1291}), **30152 ARGS rows** ({'train': 29252, 'val': 900}), catalog v3 (cloud A's `training/artifacts/catalog_v3.json`, 39 skills +
MULTI_STEP/ASK/REFUSE/ANSWER), same datum format as it2b (rendered with cloud A's `route_render` / `datums.noisy`);
Uploaded revision `84595279452d9c43573012f78555e25376316cf8` (private).
`provenance.jsonl.gz` maps every row to `it2b` or `gen:<group>`. Every change is one line in
`build/changes.jsonl` (uploaded as `changes.jsonl.gz`). No Tinker runs were started.

Code (`training/data_route/`): `audit.py` (sample, judges, adjudication), `fix.py` (full-pool re-judge),
`gen.py` (targeted generation + checks + judges), `ground.py` (deterministic ARGS grounding), `build.py`
(rules, gate, export, upload), `report.py` (this file). Judges: `gpt-5.6-sol` (OpenAI) and `claude-opus-5-5`
(Anthropic), blind to gold, with the v3 option descriptions, cloud A's v3 policy plus `policy.py` boundaries, and
the full context (app, focused, selection, online, last_action). Adjudicator `gpt-5.5` sees gold and both verdicts.

## 1. Audit of it2b (1,500 items, stratified by label, seed 0)

### Route labels
1500 items, 41 labels. Judge-judge agreement 93.2%; agreement with gold: gpt-5.6-sol 87.5%, claude-opus-5-5 86.7%. Route noise **115/1500 = 7.7%** (+9 compose_email -> draft_email catalog-v3 policy shifts, applied but not counted as noise).

| label | n | wrong | rate | final labels | examples |
|---|---|---|---|---|---|
| compose_email | 37 | 13 | 35.1% | send_message 11, ASK 2 (+9 v3 draft_email) | "Dana needs to know I'll be late to the standup." -> send_message; "Write to Ana, say thanks for dinner." -> send_message |
| web_search | 37 | 9 | 24.3% | ANSWER 5, REFUSE 4 | "I want to know who painted The Persistence of Memory." -> ANSWER; "uh I need to, I mean, search for cheap flights to Lisbon" -> REFUSE |
| open_folder | 36 | 8 | 22.2% | find_file 5, MULTI_STEP 2, open_url 1 | "I'm hunting for the Keynote slides from Monday, what folder were they " -> find_file; "Pull up the folder with my tax returns" -> find_file |
| wifi | 36 | 6 | 16.7% | ANSWER 3, ASK 1, mute 1 | "Do you have Wi‑Fi on right now?" -> ANSWER; "turn it off" -> ASK |
| media_control | 37 | 6 | 16.2% | ASK 3, MULTI_STEP 1, mute 1 | "go back" -> MULTI_STEP; "nah, let's stop this for now" -> ASK |
| copy_selection | 36 | 5 | 13.9% | MULTI_STEP 5 | "I need this whole table to show up in my spreadsheet." -> MULTI_STEP; "I want to drop this into my Notes app before I forget it." -> MULTI_STEP |
| set_volume | 36 | 5 | 13.9% | ASK 3, change_volume 1, set_brightness 1 | "Eh, let's do, um, thirty-eight, I think" -> ASK; "make it 35" -> ASK |
| create_event | 37 | 5 | 13.5% | MULTI_STEP 2, type_text 1, create_reminder 1 | "The jazz night at the Blue Room is Thursday, doors at eight." -> type_text; "Pick up Mia 5:15" -> create_reminder |
| sleep_display | 37 | 5 | 13.5% | set_brightness 4, lock_screen 1 | "Too much glare from the window on this thing, it's unreadable." -> set_brightness; "Lights are off and this monitor is still blazing." -> set_brightness |
| window_layout | 36 | 4 | 11.1% | MULTI_STEP 4 | "I want the Messages window tucked over on the right side." -> MULTI_STEP; "Can't see the timeline properly, it's way too squished." -> MULTI_STEP |
| create_reminder | 37 | 4 | 10.8% | REFUSE 3, empty_trash 1 | "Take out trash" -> empty_trash; "Turn off stove" -> REFUSE |
| move_to_trash | 37 | 4 | 10.8% | ASK 4 | "Can't believe that old Zoom recording from March is still sitting ther" -> ASK; "I’d like that note moved to Trash." -> ASK |
| open_file | 37 | 4 | 10.8% | find_file 4 | "I keep forgetting the setup steps, I need the project readme." -> find_file; "Where's the grocery list I wrote? I need it now." -> find_file |
| open_url | 36 | 3 | 8.3% | REFUSE 2, web_search 1 | "My kid needs a library book for school, the nypl catalog thing" -> REFUSE; "I'm trying to remember when the Louvre closes on Sundays" -> web_search |
| quit_app | 36 | 3 | 8.3% | media_control 2, ANSWER 1 | "stop music" -> media_control; "Spotify's still blasting in the living room and I can't hear the call" -> media_control |
| take_screenshot | 36 | 3 | 8.3% | ASK 2, MULTI_STEP 1 | "Could you preserve the Safari page as it looks right now?" -> MULTI_STEP; "Lock in just the highlighted lines from this doc." -> ASK |
| change_volume | 37 | 3 | 8.1% | ASK 2, MULTI_STEP 1 | "The movie dialogue is getting lost under the soundtrack." -> MULTI_STEP; "Go up a tiny bit." -> ASK |
| set_brightness | 37 | 3 | 8.1% | start_timer 1, ASK 1, set_volume 1 | "Make it seventy-five." -> start_timer; "Set it to 75" -> ASK |
| ASK | 36 | 2 | 5.6% | MULTI_STEP 1, send_message 1 | "Could you lock my Mac in ten minutes after I finish reading this?" -> MULTI_STEP; "Send a message to Sarah." -> send_message |
| todays_agenda | 36 | 2 | 5.6% | MULTI_STEP 1, ASK 1 | "Am I going to make it to pickup on time today?" -> MULTI_STEP; "Tell me what I have" -> ASK |
| MULTI_STEP | 37 | 2 | 5.4% | web_search 1, advisor_prep 1 | "Search “running shoes” for sale" -> web_search; "Please prepare the brief for tomorrow's meeting with the Chen househol" -> advisor_prep |
| advisor_prep | 37 | 2 | 5.4% | MULTI_STEP 2 | "Do I have a meeting with the Stantons coming up?" -> MULTI_STEP; "Can you check my calendar and pull up the Fairbanks meeting?" -> MULTI_STEP |
| dark_mode | 37 | 2 | 5.4% | set_brightness 2 | "My eyes are getting strained from this bright screen, could you darken" -> set_brightness; "It's way too dim, I can't tell what's what." -> set_brightness |
| empty_trash | 37 | 2 | 5.4% | MULTI_STEP 2 | "Could you please empty the trash, but keep the files I dropped in ther" -> MULTI_STEP; "Would you mind permanently deleting the stuff in the trash from last y" -> MULTI_STEP |
| type_text | 37 | 2 | 5.4% | new_note 1, ASK 1 | "jot down call mom" -> new_note; "could you enter this search query for me" -> ASK |
| bluetooth | 36 | 1 | 2.8% | MULTI_STEP 1 | "Would you mind disconnecting the keyboard from Bluetooth?" -> MULTI_STEP |
| hide_app | 36 | 1 | 2.8% | ASK 1 | "Could you hide Reminders? Not yet." -> ASK |
| mute | 36 | 1 | 2.8% | change_volume 1 | "Hard to follow the tutorial with no audio coming through." -> change_volume |
| new_folder | 36 | 1 | 2.8% | DROP 1 | "iCloud Drive folder, Shared" -> DROP |
| REFUSE | 37 | 1 | 2.7% | MULTI_STEP 1 | "Permanently delete my bank statement PDFs." -> MULTI_STEP |
| open_app | 37 | 1 | 2.7% | MULTI_STEP 1 | "I need to record my screen, QuickTime is what I used last time." -> MULTI_STEP |
| premiere_command | 37 | 1 | 2.7% | ASK 1 | "export using that preset" -> ASK |
| send_message | 37 | 1 | 2.7% | compose_email 1 | "Could you send Ben sorry I missed your call?" -> compose_email |
| ANSWER | 37 | 0 | 0.0% |  |  |
| battery_status | 36 | 0 | 0.0% |  |  |
| finance_review | 37 | 0 | 0.0% |  |  |
| find_file | 37 | 0 | 0.0% |  |  |
| lock_screen | 36 | 0 | 0.0% |  |  |
| new_note | 37 | 0 | 0.0% |  |  |
| play_music | 36 | 0 | 0.0% |  |  |
| start_timer | 37 | 0 | 0.0% |  |  |

Method note: the first pass used two policy lines that conflicted with cloud A's v3 policy (unclear channel -> ASK,
statements -> ASK) and measured 12.1%. They were corrected and the 190 affected items re-judged and re-adjudicated;
first-pass verdicts are kept in `audit/judged.jsonl` under `pass1:*`.

### ARGS
1061 sampled rows with an ARGS target. Wrong **167/1061 = 15.7%** (112 fixable, 55 drop).

| skill | n | fix | drop | rate | example |
|---|---|---|---|---|---|
| open_folder | 28 | 12 | 1 | 46.4% | "Pull up the folder with my tax returns" `path="tax returns folder"` -> drop |
| new_folder | 36 | 15 | 0 | 41.7% | "I'd appreciate a folder called Recipes Old on my desktop, th" `parent="my desktop" name="Recipes Old"` -> fix `parent=Desktop name="Recipes Old"` |
| mute | 36 | 6 | 8 | 38.9% | "Why is my Mac so loud right now, I'm in a meeting." `on=true` -> drop |
| change_volume | 36 | 9 | 3 | 33.3% | "The movie dialogue is getting lost under the soundtrack." `delta=10` -> drop |
| compose_email | 28 | 5 | 4 | 32.1% | "Email Ellen, thanks" `to=Ellen body=thanks` -> drop |
| quit_app | 36 | 5 | 6 | 30.6% | "stop music" `app=Music` -> drop |
| move_to_trash | 30 | 7 | 1 | 26.7% | "Please trash the file named draft_email_copy.eml on the desk" `path="draft_email_copy.eml on the desktop"` -> fix `path="Desktop/draft_email_copy.eml"` |
| find_file | 36 | 9 | 0 | 25.0% | "Can you find the photo of my grandmother's recipe card?" `query="grandmother's recipe card" kind=image` -> fix `query="my grandmother's recipe card" kind=image` |
| type_text | 36 | 6 | 1 | 19.4% | "type password reset done" `text="Password reset done"` -> fix `text="password reset done"` |
| open_file | 34 | 2 | 4 | 17.6% | "That screenshot of the error message, I need to read it clos" `path="screenshot of the error message"` -> drop |
| set_brightness | 35 | 1 | 5 | 17.1% | "Not so harsh, this is way too strong for my eyes right now." `level=55` -> drop |
| create_event | 37 | 6 | 0 | 16.2% | "hey, uh, I'm supposed to, like, see the optometrist on the t" `title=optometrist start="on the twenty-second at ten thirty"` -> fix `title="see the optometrist" start="on the twenty-second at ten thirty"` |
| start_timer | 37 | 5 | 1 | 16.2% | "Chicken needs to rest for ten minutes after it comes out." `duration="ten minutes" label="chicken rest"` -> fix `duration="ten minutes" label="Chicken needs to rest"` |
| play_music | 33 | 5 | 0 | 15.2% | "I want that Dua Lipa album from last summer." `query="Dua Lipa"` -> fix `query="Dua Lipa album from last summer"` |
| create_reminder | 35 | 5 | 0 | 14.3% | "Remind me to buy a birthday card for Jake by Friday" `title="buy birthday card for Jake" due="by Friday"` -> fix `title="buy a birthday card for Jake" due="by Friday"` |
| open_app | 37 | 4 | 1 | 13.5% | "uh, mail, open mail, um, there's an email I, like, missed" `app=mail` -> fix `app=Mail` |
| wifi | 35 | 0 | 4 | 11.4% | "Do you have Wi‑Fi on right now?" `on=true` -> drop |
| advisor_prep | 36 | 1 | 3 | 11.1% | "Do I have a meeting with the Stantons coming up?" `client=Stantons` -> drop |
| open_url | 36 | 3 | 1 | 11.1% | "My kid needs a library book for school, the nypl catalog thi" `url=catalog.nypl.org` -> fix `url=nypl.org` |
| media_control | 37 | 0 | 3 | 8.1% | "this track is so boring" `action=next` -> drop |
| finance_review | 29 | 0 | 2 | 6.9% | "Can you reconcile receipts and tell me where I’m over budget" `task=all` -> drop |
| new_note | 29 | 2 | 0 | 6.9% | "so yeah, could you note, um, that Dave's birthday is the twe" `body="that Dave's birthday is the twelfth of March"` -> fix `body="Dave's birthday is the twelfth of March"` |
| hide_app | 35 | 1 | 1 | 5.7% | "hide mail now" `app=mail` -> fix `app="Mail"` |
| web_search | 35 | 2 | 0 | 5.7% | "Who was the guy that invented the telephone again" `query="who invented the telephone"` -> fix `query="Who was the guy that invented the telephone again"` |
| set_volume | 36 | 0 | 2 | 5.6% | "Need it nearly silent, I'm on a call in a minute" `level=3` -> drop |
| dark_mode | 37 | 0 | 2 | 5.4% | "It's way too dim, I can't tell what's what." `on=false` -> drop |
| take_screenshot | 28 | 0 | 1 | 3.6% | "Could that Safari page with the receipt be saved somehow?" `region=window` -> drop |
| bluetooth | 33 | 0 | 1 | 3.0% | "Gonna need my earbuds for this meeting and they're nowhere t" `on=true` -> drop |
| send_message | 34 | 1 | 0 | 2.9% | "text Mike, I've got the tickets, wait, no, tell him I'll get" `to=Mike body="I'll get the tickets"` -> fix `to=Mike body="I'll get them"` |
| premiere_command | 35 | 0 | 0 | 0.0% |  |
| window_layout | 36 | 0 | 0 | 0.0% |  |

### Full-pool re-judge (rule R3)
Labels with >= 13% audit noise or flagged weak by the lead.

7369 rows (every non-sampled row of the 10 labels), same two judges + gpt-5.5 adjudicator. 1082 changed (14.7%).

| label | rows | changed | rate | new labels |
|---|---|---|---|---|
| compose_email | 790 | 347 | 43.9% | draft_email 183, send_message 74, ASK 62, MULTI_STEP 16 |
| set_volume | 685 | 113 | 16.5% | ASK 77, change_volume 30, mute 3, set_brightness 2 |
| open_folder | 586 | 94 | 16.0% | find_file 67, MULTI_STEP 10, ASK 7, ANSWER 4 |
| media_control | 796 | 105 | 13.2% | ASK 50, premiere_command 24, mute 12, change_volume 7 |
| sleep_display | 722 | 92 | 12.7% | set_brightness 57, lock_screen 13, ASK 11, MULTI_STEP 5 |
| create_event | 943 | 119 | 12.6% | create_reminder 45, ASK 42, type_text 17, MULTI_STEP 13 |
| copy_selection | 586 | 59 | 10.1% | MULTI_STEP 36, ASK 19, send_message 2, type_text 1 |
| web_search | 799 | 73 | 9.1% | ANSWER 69, ASK 2, open_url 1, find_file 1 |
| set_brightness | 819 | 46 | 5.6% | ASK 27, set_volume 18, change_volume 1 |
| wifi | 643 | 34 | 5.3% | ASK 21, MULTI_STEP 8, mute 2, lock_screen 1 |

## 2. Rules applied (never silent; counts from `meta.json`)

- R1 context: `web_search` / `open_url` rows with `online=false` -> `online=true` (the label needs the web).
- R2 audited rows: final label = gold when both judges agree with it, else the adjudicator's label; DROP/unresolved
  removed. ARGS take the adjudicator's verdict (fix -> its fixed target after `norm_args`, drop -> removed).
- R3 full-pool re-judge of the 10 labels above, same decision rule as R2.
- R4 ARGS grounding (`ground.py`): drop an ARGS row whose values neither appear in the utterance nor follow by the
  documented coercions (spoken numbers, max/half, a bit/a lot deltas, on/off, enum words, canonical app names,
  site name -> domain, unit spellings). The route row stays.
- R5 `change_volume`: delta re-derived from the spoken amount and direction (incl. self-corrections).
- R6 ARGS of a route row whose label changed (R2/R3) or was dropped are removed. R6b: 562 it2b ARGS rows whose skill
  is not the route label of the same utterance (e.g. "mute it" with `set_volume` ARGS) are removed.
  ARGS-only rows (no route row in it2b) are kept and go through R4/R5/R7.
- R7 `open_folder` path: the/my and a trailing "folder" dropped, well-known folders capitalized (path=desktop ->
  Desktop).
- G generated rows kept only if both judges pick the intended label and both ARGS judges accept the target.
- D decontamination gate (below); hits are dropped from route and ARGS.

| rule:kind | rows |
|---|---|
| R3:route_relabel | 1073 |
| R2:route_relabel | 123 |
| R3:route_drop | 9 |
| R1:context_online | 160 |
| R2:route_drop | 1 |
| R6:args_drop_relabel | 1023 |
| R4:args_drop_ungrounded | 147 |
| R2:args_drop | 33 |
| R2:args_fix | 101 |
| R6b:args_drop_inconsistent | 562 |
| R7:args_fix | 95 |
| R5:args_fix | 67 |
| D:gate_drop | 156 |

Examples:
- D: {"rule": "D", "kind": "gate_drop", "utterance": "message my sister", "eval": "route_v2", "eval_utterance": "iMessage my sister", "overlap": "short_edit1"} / {"rule": "D", "kind": "gate_drop", "utterance": "text her", "eval": "route_v1", "eval_utterance": "email her", "overlap": "short_edit1"}
- R1: {"rule": "R1", "kind": "context_online", "utterance": "google dog bite help", "label": "web_search"} / {"rule": "R1", "kind": "context_online", "utterance": "search yoga near me", "label": "web_search"}
- R2: {"rule": "R2", "kind": "route_relabel", "utterance": "Mom would want to know we landed safely", "label": "compose_email", "new": "send_message"} / {"rule": "R2", "kind": "route_relabel", "utterance": "Dave still doesn't know the invoice got approved", "label": "compose_email", "new": "send_message"}
- R3: {"rule": "R3", "kind": "route_relabel", "utterance": "Jordan's probably wondering if that report is done yet", "label": "compose_email", "new": "send_message"} / {"rule": "R3", "kind": "route_relabel", "utterance": "I keep forgetting to tell Priya the meeting moved to three", "label": "compose_email", "new": "create_reminder"}
- R4: {"rule": "R4", "kind": "args_drop_ungrounded", "utterance": "Word's been open since yesterday and I'm completely done with that doc.", "skill": "quit_app", "target": "app=\"Microsoft Word\"", "why": "app:Microsoft Word"} / {"rule": "R4", "kind": "args_drop_ungrounded", "utterance": "QuickTime's still got that video up and I'm done watching it.", "skill": "quit_app", "target": "app=\"QuickTime Player\"", "why": "app:QuickTime Player"}
- R5: {"rule": "R5", "kind": "args_fix", "utterance": "Um, so yeah, I can't really hear this, like, bump it up a bit?", "skill": "change_volume", "target": "delta=25", "new": "delta=10"} / {"rule": "R5", "kind": "args_fix", "utterance": "I- I mean, can you raise the volume, like, by twenty or so?", "skill": "change_volume", "target": "delta=10", "new": "delta=20"}
- R6: {"rule": "R6", "kind": "args_drop_relabel", "utterance": "Jordan's probably wondering if that report is done yet", "skill": "compose_email", "target": "to=Jordan body=\"that report is done\"", "route": "send_message"} / {"rule": "R6", "kind": "args_drop_relabel", "utterance": "I keep forgetting to tell Priya the meeting moved to three", "skill": "compose_email", "target": "to=Priya body=\"the meeting moved to three\"", "route": "create_reminder"}
- R6b: {"rule": "R6b", "kind": "args_drop_inconsistent", "utterance": "Notes folder in Documents?", "skill": "new_folder", "target": "parent=Documents name=Notes", "route": ["open_folder"]} / {"rule": "R6b", "kind": "args_drop_inconsistent", "utterance": "My cousin posted her Etsy shop last week and I can't find it again", "skill": "open_url", "target": "url=etsy.com", "route": ["ASK"]}
- R7: {"rule": "R7", "kind": "args_fix", "utterance": "uh, can you, like, open my downloads, sorry, I mean the downloads folder", "skill": "open_folder", "target": "path=downloads", "new": "path=Downloads"} / {"rule": "R7", "kind": "args_fix", "utterance": "hey, um, I need the desktop folder, like, open that in finder maybe", "skill": "open_folder", "target": "path=desktop", "new": "path=Desktop"}

## 3. Targeted generation

Groups (`gen.py`): email (compose_email / send_message / draft_email / ASK minimal pairs across the channel
boundary), messaging (named people, with and without a body), writing + writing2 (compose_text / new_note /
type_text / draft_email), sites (bare site names -> open_url vs Mac apps vs web_search), media (media_control vs
premiere_command vs play_music), files (open_folder vs open_file vs find_file vs open_app), display
(set_brightness vs dark_mode vs change_volume / set_volume / mute / sleep_display). Writers `claude-sonnet-5-5`
and `gpt-5.6-sol`; style mix with ~40% ASR-style transcripts (lowercase, no punctuation, fillers, restarts,
self-corrections, homophones, spelled numbers); contexts vary frontmost app, focused element and selection.

Checks before judging: label in group, context consistency (premiere_command needs Premiere Pro, type_text a
focused text field), `norm_args`, `ground.py`, required/missing arguments, normalized dedup. 1648 passed;
1378 kept after the judges, dedup against the pool and the gate. Second ARGS pass: the first ARGS judge prompt
did not state cloud A's v3 target conventions (send_message `missing=body`, compose_text `target=notes` default),
so items rejected only on ARGS were re-judged once with them stated (`gen.py rejudge_args`).

Rows by source: `{"it2b": 40378, "gen:email": 275, "gen:messaging": 156, "gen:writing": 189, "gen:sites": 140, "gen:media": 134, "gen:files": 167, "gen:display": 147, "gen:writing2": 170}`

Rejected: `{"args_judges": 68, "dup_of_pool": 69, "route_judges:ASK->send_message/send_message": 14, "route_judges:compose_email->compose_email/draft_email": 6, "route_judges:compose_email->send_message/send_message": 1, "route_judges:draft_email->ASK/draft_email": 1, "route_judges:ASK->MULTI_STEP/MULTI_STEP": 1, "route_judges:compose_email->draft_email/draft_email": 1, "route_judges:ASK->send_message/MULTI_STEP": 4, "route_judges:ASK->ASK/send_message": 1, "route_judges:ASK->send_message/ASK": 1, "route_judges:compose_text->web_search/web_search": 1, "route_judges:compose_text->ASK/compose_text": 6, "route_judges:new_note->new_note/create_reminder": 2, "route_judges:draft_email->send_message/send_message": 1, "route_judges:compose_text->web_search/compose_text": 1, "route_judges:open_app->open_folder/ASK": 1, "route_judges:open_url->open_url/ASK": 1, "route_judges:open_app->ASK/media_control": 1, "route_judges:open_app->MULTI_STEP/open_app": 1, "route_judges:web_search->web_search/MULTI_STEP": 1, "route_judges:open_app->send_message/send_message": 1, "route_judges:play_music->ASK/play_music": 1, "route_judges:open_folder->open_folder/find_file": 1, "route_judges:find_file->web_search/MULTI_STEP": 1, "route_judges:open_folder->ASK/ASK": 1, "route_judges:open_file->find_file/open_file": 2, "route_judges:open_folder->find_file/find_file": 1, "route_judges:open_file->MULTI_STEP/open_file": 1, "route_judges:open_file->open_file/find_file": 1, "route_judges:find_file->web_search/find_file": 1, "route_judges:mute->MULTI_STEP/mute": 1, "route_judges:mute->MULTI_STEP/MULTI_STEP": 1, "route_judges:change_volume->MULTI_STEP/MULTI_STEP": 1, "route_judges:compose_text->type_text/compose_text": 1, "route_judges:compose_text->draft_email/compose_text": 2}`

## 4. Decontamination gate

cloud A's `muselet_train.evalcheck.overlaps` (normalized exact, shared 13-gram, token edit <= 1 when either side
has <= 5 tokens; `decontam.norm`, CJK characters one token each) over every route utterance, its rendered noisy
form, and every ARGS utterance, against:

| eval set | items |
|---|---|
| route_v1 | 140 |
| live_t1 | 43 |
| route_v2 | 955 |
| external/deskmind/diag | 13 |
| external/deskmind/dyn | 64 |
| external/deskmind/proposals | 22 |
| external/hobbylm/calc-tasks/dev | 4 |
| external/hobbylm/calc-tasks/held-out | 30 |
| external/hobbylm/sealed-r1 | 95 |
| external/hobbylm/sealed-r2 | 95 |
| external/hobbylm/sealed-r3 | 107 |
| external/hobbylm/sealed-r4 | 125 |
| external/hobbylm/system-settings | 15 |

Before: 156 hits, by rule {"short_edit1": 143, "exact": 13}, by eval {"route_v2": 2, "route_v1": 35, "external/hobbylm/sealed-r1": 30, "external/hobbylm/sealed-r2": 46, "external/hobbylm/sealed-r3": 18, "live_t1": 12, "external/hobbylm/sealed-r4": 13}. By source: gen exact 13, gen short_edit1 137, it2b short_edit1 6 (the 6 it2b hits are token-edit-1
near-duplicates of route_v1 / HobbyLM sealed-r3 / live_t1 short items). All dropped (rule D).
**After: 0 on every rule and every set.**

## 5. Counts

| route label | it2b | it3cand | delta |
|---|---|---|---|
| MULTI_STEP | 5349 | 5464 | +115 |
| ANSWER | 3660 | 3744 | +84 |
| REFUSE | 2246 | 2254 | +8 |
| find_file | 1114 | 1247 | +133 |
| send_message | 832 | 1153 | +321 |
| create_reminder | 1036 | 1081 | +45 |
| dark_mode | 949 | 970 | +21 |
| open_app | 893 | 957 | +64 |
| open_file | 913 | 956 | +43 |
| finance_review | 943 | 943 | +0 |
| new_note | 828 | 922 | +94 |
| set_brightness | 856 | 915 | +59 |
| create_event | 980 | 856 | -124 |
| type_text | 741 | 852 | +111 |
| premiere_command | 772 | 844 | +72 |
| ASK | 451 | 834 | +383 |
| change_volume | 762 | 826 | +64 |
| move_to_trash | 830 | 826 | -4 |
| advisor_prep | 827 | 826 | -1 |
| web_search | 836 | 818 | -18 |
| empty_trash | 774 | 773 | -1 |
| start_timer | 768 | 770 | +2 |
| play_music | 716 | 765 | +49 |
| media_control | 833 | 764 | -69 |
| new_folder | 740 | 739 | -1 |
| window_layout | 724 | 720 | -4 |
| todays_agenda | 703 | 701 | -2 |
| lock_screen | 686 | 701 | +15 |
| bluetooth | 689 | 688 | -1 |
| mute | 649 | 682 | +33 |
| open_url | 636 | 679 | +43 |
| sleep_display | 759 | 673 | -86 |
| battery_status | 653 | 654 | +1 |
| set_volume | 721 | 653 | -68 |
| take_screenshot | 647 | 644 | -3 |
| wifi | 679 | 639 | -40 |
| quit_app | 602 | 602 | +0 |
| open_folder | 622 | 559 | -63 |
| copy_selection | 622 | 558 | -64 |
| compose_email | 827 | 527 | -300 |
| hide_app | 520 | 520 | +0 |
| draft_email | 0 | 330 | +330 |
| compose_text | 0 | 127 | +127 |

| ARGS skill | rows |
|---|---|
| find_file | 1179 |
| dark_mode | 1105 |
| send_message | 1016 |
| open_app | 990 |
| create_reminder | 967 |
| premiere_command | 955 |
| media_control | 940 |
| open_file | 916 |
| set_brightness | 891 |
| type_text | 878 |
| play_music | 857 |
| change_volume | 821 |
| sleep_display | 820 |
| window_layout | 818 |
| new_note | 810 |
| todays_agenda | 805 |
| create_event | 804 |
| empty_trash | 800 |
| advisor_prep | 799 |
| web_search | 795 |
| battery_status | 794 |
| start_timer | 792 |
| finance_review | 792 |
| wifi | 778 |
| bluetooth | 770 |
| lock_screen | 758 |
| new_folder | 753 |
| mute | 753 |
| quit_app | 732 |
| open_url | 727 |
| take_screenshot | 688 |
| set_volume | 672 |
| copy_selection | 671 |
| move_to_trash | 605 |
| hide_app | 569 |
| open_folder | 552 |
| compose_email | 515 |
| draft_email | 138 |
| compose_text | 127 |

## 6. API spend

| model | calls | input tok | output tok | USD |
|---|---|---|---|---|
| gpt-5.6-sol | 604 | 1,490,244 | 802,522 | $22.01 |
| claude-opus-5-5 | 672 | 2,413,523 | 849,682 | $26.65 |
| gpt-5.5 | 147 | 431,282 | 288,841 | $10.82 |
| claude-sonnet-5-5 | 32 | 120,289 | 145,013 | $1.69 |

**Total $61.17** of the $80 budget (prices in `common.py`, USD per M tokens, conservative list prices).
