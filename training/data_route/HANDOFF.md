# data-route handoff (it3cand)

**Residue** means rows still in it3cand where at least one of the two frontier judges (gpt-5.6-sol, claude-opus-5-5) voted
against the final label after rules R2/R3. The base is 8,859 judged rows: the 1,500 audit rows plus 7,369 re-judged rows.
Counts are judge votes, so a row that both judges disputed counts twice. These rows are the labels most likely to be
contested in it3, and are a good place to check it3 val/eval confusions first. Source: `audit/judged.jsonl`,
`fix/judged.jsonl` (no new API calls; $0 spent for this note).

## 10 noisiest remaining label pairs

| # | pair | votes | typical residue (final -> dissent) |
|---|---|---|---|
| 1 | compose_email / draft_email | 122 | "Email Derek and tell him the files are in the shared folder." compose_email -> draft_email: dictated words vs "write it for me" |
| 2 | find_file / open_folder | 54 | "um the ebooks folder, the Kindle one, could you open that" open_folder -> find_file: named but unlocated folder |
| 3 | ASK / create_event | 50 | "Lab meeting 9:30am" (Safari) create_event -> ASK: bare event fragments without a verb |
| 4 | create_event / create_reminder | 48 | "Add dentist Friday" create_reminder -> create_event: no time, unclear event vs to-do |
| 5 | set_brightness / sleep_display | 45 | "Screen down." sleep_display -> set_brightness; eye-strain complaints |
| 6 | copy_selection / MULTI_STEP | 42 | "This recipe is going in my notes app, so grab it." copy_selection -> MULTI_STEP: copy plus destination |
| 7 | media_control / ASK | 35 | "Stop it for now." (Terminal) media_control -> ASK: nothing known to be playing |
| 8 | send_message / ASK | 34 | "Ellen would probably like the agenda before tomorrow" ASK -> send_message: indirect need, named person |
| 9 | web_search / ANSWER | 33 | "look up convert miles to km" web_search -> ANSWER: "look up" plus a self-answerable question |
| 10 | create_event / MULTI_STEP | 33 | "Can you book a dentist appointment on October 5th at 2 pm?" create_event -> MULTI_STEP: "book" implies an outside booking |

Runners-up: ASK/MULTI_STEP 32, ASK/copy_selection 29, create_event/type_text 25 (event-like text with a text field
focused), ASK/set_volume 25 ("max it out" with no volume context). In generation, the most common disagreement
was ASK/send_message (34 votes, unknown vs implied recipient). The pairs are mostly policy-boundary cases, not
random noise. Pairs 1, 4, 6 and 10 would be best fixed by a sharper written rule in the v3 policy, followed by a
re-judge. More data would not fix them.

## Three generation groups to expand next (if it3 eval shows weak spots)

1. **calendar** (new group): create_event vs create_reminder vs ASK vs MULTI_STEP vs type_text. This covers 4 of the
   top 10 pairs plus a runner-up, and no it3cand group targeted it. Write minimal pairs:
   - event with time vs to-do without time;
   - bare fragments, with and without a focused text field;
   - "book/reserve" (MULTI_STEP) vs "put on my calendar" (create_event).
2. **email** (expand): compose_email vs draft_email vs send_message vs ASK. This is still the largest residue,
   ranked #1 and #8. Write pairs that differ only in "say X" (dictated words) vs "write/tell them about X" (draft), and
   indirect named-person needs vs no recipient. First add one policy sentence on what counts as dictated words.
3. **referent-less controls** (new group): media_control / set_volume / set_brightness / sleep_display / copy_selection
   vs ASK. These are bare "stop it", "max it out", "screen down", "copy this" commands. Vary `last_action` and the frontmost app so
   the same words resolve to the skill when the context supplies the referent, and to ASK when it doesn't. it3cand set
   `last_action` on only ~10% of generated rows, so this context is under-represented.

Each group needs ~150-300 kept rows at the it3cand acceptance rate (~82%, both judges agree). That costs about $3-5 per
group with the existing `gen.py` writers and judges.
