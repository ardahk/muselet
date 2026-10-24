# memory_followups: frozen multi-turn follow-up eval set

`evals/memory_followups.jsonl`: 200 sequences of 2-5 turns for the lead-owned scorer `evals/memory_eval.py`. Data only. **Holdout items are never to be read, printed, trained or tuned on**; develop against `split == "tune"`. Structure lint: `python3 evals/memory_followups_lint.py` (test: `bench/tests/test_memory_followups_lint.py`).

## Counts

| category | tune | holdout | total | turns | rewrite | not_resolved | unchanged |
|---|---|---|---|---|---|---|---|
| site_search | 15 | 15 | 30 | 84 | 47 | 0 | 37 |
| pronoun_person | 10 | 10 | 20 | 54 | 18 | 5 | 31 |
| pronoun_item | 10 | 10 | 20 | 49 | 23 | 4 | 22 |
| again | 8 | 7 | 15 | 35 | 11 | 4 | 20 |
| undo | 8 | 7 | 15 | 45 | 12 | 6 | 27 |
| correction | 8 | 7 | 15 | 41 | 14 | 2 | 25 |
| refinement | 8 | 7 | 15 | 39 | 22 | 0 | 17 |
| stale | 8 | 7 | 15 | 44 | 1 | 13 | 30 |
| unrelated | 15 | 15 | 30 | 80 | 3 | 0 | 77 |
| longterm | 13 | 12 | 25 | 68 | 45 | 0 | 23 |
| **all** | 103 | 97 | 200 | 539 | 196 | 34 | 309 |

Apps in ctx (turns): Google Chrome 59, Finder 46, Safari 42, Calendar 35, Messages 32, Premiere Pro 29, Zen 28, Spotify 28, Mail 27, Terminal 27, Notes 26, Music 26, Slack 24, Numbers 23, Pages 22, System Settings 19, Reminders 16, TextEdit 15, Preview 14, Keynote 1.

## Blind judge agreement

Generator: Anthropic `claude-opus-5-5`. Judge: OpenAI `gpt-5.6-sol`, blind (it sees only the sequence: no generator rationale, no provenance, no other items' verdicts) and asked per turn: does the expectation match what a reasonable user means, are the `all` groups fair to valid paraphrases (URL and phrase forms), do they cover the content a wrong resolution would drop, can a correct resolution contain a `none` term, are outcomes/ctx consistent with history, does it fit the category. A sequence is `agree` only if every turn is ok. Disagreements were sent back to the generator with the judge's critique (fix or drop), then the revised sequence was re-judged blind from scratch; only sequences whose **final version** the judge agreed with were eligible. Every one of the 200 shipped sequences is judge-agreed in its shipped form.

| category | candidates | first-pass agree | all judgments agree | eligible | shipped | shipped after repair |
|---|---|---|---|---|---|---|
| site_search | 46 | 21/46 (46%) | 43/71 (61%) | 43 | 30 | 15 |
| pronoun_person | 28 | 17/28 (61%) | 26/49 (53%) | 24 | 20 | 7 |
| pronoun_item | 28 | 13/28 (46%) | 23/51 (45%) | 23 | 20 | 8 |
| again | 21 | 7/21 (33%) | 18/36 (50%) | 17 | 15 | 9 |
| undo | 25 | 9/21 (43%) | 19/45 (42%) | 19 | 15 | 5 |
| correction | 25 | 4/21 (19%) | 22/49 (45%) | 22 | 15 | 10 |
| refinement | 36 | 0/21 (0%) | 21/96 (22%) | 21 | 15 | 13 |
| stale | 21 | 21/21 (100%) | 21/22 (95%) | 20 | 15 | 0 |
| unrelated | 40 | 34/40 (85%) | 37/47 (79%) | 36 | 30 | 2 |
| longterm | 39 | 17/35 (49%) | 32/69 (46%) | 31 | 25 | 9 |

Main disagreement themes (all fixed or dropped): `all` groups missing a meaning-carrying query word ("slow" cooker, "near the train"); groups too wording-specific ("upbeat" vs "energetic", "8" vs "eight"); `none` terms that a correct contrastive correction can contain ("send it to Rosa, not Malik"); `create_reminder` used to *edit* an existing reminder (rewritten to `planner` or dropped).

## Recipe

Scratch pipeline (not committed; prompts summarized here): (1) per-category generation prompts with the 39-skill catalog (`skills/catalog.json`, plus `planner` {goal} and `ASK` {question}), site names from `ml/src/brain/sites.py`, app list and the lane brief's rules, 4-6 sequences per call (top-up batches 4-5); (2) automatic checks (schema, catalog skill/arg names and enums, browser<->url, increasing `t`, rewrite groups non-empty with alternatives >= 2 chars, generator-written reference resolutions must pass every rewrite check while the raw utterance must fail it); (3) blind judge; (4) fix rounds (up to 3) + re-judge; (5) assembly with seed `20261024`: per category, candidates sorted by generation id and shuffled with `random.Random(20261024)`, near-duplicates dropped (token-set Jaccard >= 0.6 over all utterances vs. every kept sequence), first quota kept; split: per category shuffled with `random.Random('20261024-<category>')`, first ceil(n/2) tune, rest holdout; ids `mf-0001..` in category order.

Semantics: `ctx` is the state at push-to-talk (before the turn's action); `outcome` is what correctly happened (the resolved action) and is what later turns may refer to. `longterm` rewrite groups require the stored value (e.g. "jane"), because the raw utterance already contains the key ("mom"). `none` never lists a corrected-away referent. Names are fictional; no real personal data.

## Spend

Anthropic (generation + repair) ~$17.27, OpenAI (judging) ~$14.53 (estimated from token usage at list prices; cap $30 each). No Tinker.

## 20 random tune examples (seed 20261024)

### mf-0004 (site_search)
0. t=0 Preview | "open stack over flow" -> `open_url {"url": "https://stackoverflow.com"}` | unchanged
1. t=11 Safari https://stackoverflow.com/ | "look up segfault in strtok" -> `open_url {"url": "https://stackoverflow.com/search?q=segfault+strtok"}` | rewrite all=[["stack overflow", "stackoverflow"], ["segfault"], ["strtok"]] none=["google"]

### mf-0016 (site_search)
0. t=0 Slack | "go to youtube" -> `open_url {"url": "https://www.youtube.com"}` | unchanged
1. t=6 Zen https://www.youtube.com/ | "serch for ten minute morning yoga" -> `open_url {"url": "https://www.youtube.com/results?search_query=10+minute+morning+yoga"}` | rewrite all=[["youtube"], ["morning"], ["yoga"], ["10", "ten"], ["minute", "min"]] none=["google", "standup"]

### mf-0019 (site_search)
0. t=0 Premiere Pro | "add a marker" -> `premiere_command {"command": "add_marker"}` | unchanged
1. t=35 Google Chrome https://www.reddit.com/r/premiere/ | "look up audio drifting out of sync" -> `open_url {"url": "https://www.reddit.com/r/premiere/search/?q=audio+drifting+out+of+sync"}` | rewrite all=[["reddit"], ["premiere"], ["audio"], ["drift"], ["sync"]] none=["google"]

### mf-0022 (site_search)
0. t=0 Mail | "go to stack overflow" -> `open_url {"url": "https://stackoverflow.com"}` | unchanged
1. t=9 Safari https://stackoverflow.com/ | "serch for imap idle timeout" -> `open_url {"url": "https://stackoverflow.com/search?q=imap+idle+timeout"}` | rewrite all=[["stack overflow", "stackoverflow"], ["imap"], ["idle"], ["timeout"]] none=["google"]

### mf-0045 (pronoun_person)
0. t=0 Terminal | "message Marcus that the deploy script finished" -> `send_message {"to": "Marcus", "body": "The deploy script finished."}` | unchanged
1. t=30 Terminal | "oh and tell him the cron job runs at six am now" -> `send_message {"to": "Marcus", "body": "The cron job runs at 6 AM now."}` | rewrite all=[["marcus"], ["cron"]] none=[]

### mf-0047 (pronoun_person)
0. t=0 Mail | "draft an email to Priya saying the quarterly budget sheet is ready" -> `compose_email {"to": "Priya", "subject": "Quarterly budget", "body": "The quarterly budget sheet is ready."}` | unchanged
1. t=14 Mail | "open the budget twenty twenty five numbers file" -> `open_file {"path": "~/Documents/Budget 2025.numbers"}` | unchanged
2. t=52 Numbers | "uh tex her that the rent line is over by two hundred" -> `send_message {"to": "Priya", "body": "Heads up, the rent line is over by $200."}` | rewrite all=[["priya"], ["rent"]] none=[]
3. t=75 Numbers | "remind me to call her at noon" -> `create_reminder {"title": "Call Priya", "due": "today 12:00"}` | rewrite all=[["priya"], ["call"]] none=[]

### mf-0080 (again)
0. t=0 Spotify | "turn it down like 15" -> `change_volume {"delta": -15}` | unchanged
1. t=9 Spotify | "uh agin" -> `change_volume {"delta": -15}` | rewrite all=[["volume", "audio", "sound"], ["down", "lower", "decrease", "reduce", "quieter", "-15"], ["15", "fifteen"]] none=[]

### mf-0086 (undo)
0. t=0 Pages | "set brightness to 40" -> `set_brightness {"level": 40}` | unchanged
1. t=21 Pages | "hmm i can't read the numbers, crank it all the way up" -> `set_brightness {"level": 100}` | rewrite all=[["brightness"], ["100", "hundred", "max"]] none=[]
2. t=34 Pages | "okay that's blinding, go back to how it was" -> `set_brightness {"level": 40}` | rewrite all=[["brightness"], ["40", "forty"]] none=["100", "hundred"]

### mf-0087 (undo)
0. t=0 Slack | "dark mode on" -> `dark_mode {"on": true}` | unchanged
1. t=7 Slack | "and set the volume to 25" -> `set_volume {"level": 25}` | unchanged
2. t=48 Slack | "uh turn the volume down ten" -> `change_volume {"delta": -10}` | unchanged
3. t=61 Slack | "nah i can't hear the huddle, undo that" -> `change_volume {"delta": 10}` | rewrite all=[["volume"], ["up", "raise", "increase", "louder", "+10", "25", "twenty-five", "twenty five"]] none=["dark mode", "light"]

### mf-0101 (correction)
0. t=0 Finder | "open my downloads" -> `open_folder {"path": "~/Downloads"}` | unchanged
1. t=7 Finder | "make a new folder called halloween party" -> `new_folder {"parent": "~/Downloads", "name": "halloween party"}` | unchanged
2. t=15 Finder | "ugh wrong folder, put it in documents" -> `planner {"goal": "move the halloween party folder from Downloads to Documents"}` | rewrite all=[["documents"], ["halloween"], ["move", "put"]] none=[]

### mf-0125 (refinement)
0. t=0 Google Chrome https://www.google.com/ | "serch premier league fixtures" -> `web_search {"query": "premier league fixtures"}` | unchanged
1. t=14 Google Chrome https://www.google.com/search?q=premier+league+fixtures | "just arsenal" -> `web_search {"query": "arsenal premier league fixtures"}` | rewrite all=[["arsenal"], ["premier", "epl"], ["fixture", "schedule", "game", "match"]] none=[]
2. t=37 Google Chrome https://www.google.com/search?q=arsenal+premier+league+fixtures | "uh only the away games" -> `web_search {"query": "arsenal away fixtures premier league"}` | rewrite all=[["arsenal"], ["premier", "epl"], ["away"], ["fixture", "schedule", "game", "match"]] none=[]

### mf-0127 (refinement)
0. t=0 Safari https://www.apple.com/startpage/ | "serch for local news about the riverside library closure" -> `web_search {"query": "local news riverside library closure"}` | unchanged
1. t=14 Safari https://www.google.com/search?q=local+news+riverside+library+closure | "just from this week" -> `web_search {"query": "riverside library closure news this week"}` | rewrite all=[["riverside"], ["library"], ["clos"], ["week", "7 days", "seven days", "qdr:w", "qdr%3aw"]] none=[]

### mf-0132 (stale)
0. t=0 Preview | "take a screenshot of this window" -> `take_screenshot {"region": "window"}` | unchanged
1. t=3600 Safari https://www.bbc.com/news | "open that pdf again" -> `ASK {"question": "Which PDF would you like me to open?"}` | not_resolved
2. t=3650 Safari https://www.bbc.com/news | "find the pdf called embargo schedule" -> `find_file {"query": "embargo schedule", "kind": "pdf"}` | unchanged

### mf-0139 (stale)
0. t=0 TextEdit | "type good morning lincoln middle school today's lunch is tacos" -> `type_text {"text": "Good morning Lincoln Middle School, today's lunch is tacos."}` | unchanged
1. t=20 TextEdit | "copy that" -> `copy_selection {}` | unchanged
2. t=2900 Slack | "send that to priya" -> `ASK {"question": "What would you like to send to Priya?"}` | not_resolved

### mf-0148 (unrelated)
0. t=0 Terminal | "take a screenshot of this window" -> `take_screenshot {"region": "window"}` | unchanged
1. t=17 Terminal | "text Aiko the wifi password is on the fridge" -> `send_message {"to": "Aiko", "body": "the wifi password is on the fridge"}` | unchanged

### mf-0156 (unrelated)
0. t=0 Notes | "make a note called commute podcast ideas saying interview a bike courier" -> `new_note {"title": "Commute podcast ideas", "body": "Interview a bike courier"}` | unchanged
1. t=16 Notes | "open the movies folder" -> `open_folder {"path": "Movies"}` | unchanged

### mf-0163 (unrelated)
0. t=0 Premiere Pro | "razor at the play head" -> `premiere_command {"command": "razor_at_playhead"}` | unchanged
1. t=14 Premiere Pro | "make a note uh swap the b-roll in scene four" -> `new_note {"body": "Swap the b-roll in scene four"}` | unchanged
2. t=47 Premiere Pro | "export with the YouTube 1080p preset" -> `premiere_command {"command": "export", "preset": "YouTube 1080p"}` | unchanged

### mf-0179 (longterm) longterm: [{"type": "preference", "key": "party playlist", "value": "Motown Classics"}, {"type": "person", "key": "uncle", "value": "Dmitri Volkov"}]
0. t=0 Music | "play september by earth wind and fire" -> `play_music {"query": "September Earth, Wind & Fire"}` | unchanged
1. t=47 Music | "skip to the next song" -> `media_control {"action": "next"}` | unchanged

### mf-0183 (longterm) longterm: [{"type": "file", "key": "budget sheet", "value": "~/Documents/Budget/Household 2025.numbers"}, {"type": "person", "key": "sis", "value": "Aiyana Brooks"}, {"type": "place", "key": "the cabin", "value": "12 Pine Hollow Rd, Big Bear Lake"}]
0. t=0 Finder | "open my budget sheet" -> `open_file {"path": "~/Documents/Budget/Household 2025.numbers"}` | rewrite all=[["household"], ["2025", "twenty twenty-five", "twenty twenty five", "two thousand twenty-five", "two thousand twenty five", "two thousand and twenty-five", "two thousand and twenty five", "two zero two five"]] none=[]
1. t=19 Numbers | "find any duplicate charges" -> `finance_review {"task": "duplicates"}` | unchanged
2. t=64 Numbers | "tex my sis that her share of the weekend groceries is forty two dollars" -> `send_message {"to": "Aiyana Brooks", "body": "Your share of the weekend groceries is $42."}` | rewrite all=[["aiyana", "brooks"], ["weekend"], ["grocer"], ["42", "forty-two", "forty two"]] none=[]

### mf-0187 (longterm) longterm: [{"type": "person", "key": "sis", "value": "Priya Nair"}, {"type": "site", "key": "stock footage site", "value": "https://footage.example.com"}, {"type": "preference", "key": "focus music", "value": "synthwave"}]
0. t=0 Zen https://www.youtube.com/ | "search the web for how to fix flicker in timelapse footage" -> `web_search {"query": "how to fix flicker in timelapse footage"}` | unchanged
1. t=34 Zen https://www.google.com/search?q=how+to+fix+flicker+in+timelapse+footage | "dim the screen to twenty percent" -> `set_brightness {"level": 20}` | unchanged
2. t=70 Zen https://www.google.com/search?q=how+to+fix+flicker+in+timelapse+footage | "uh set a timer for 45 minutes called export check" -> `start_timer {"duration": "45m", "label": "export check"}` | unchanged

