"""recovery: the last batch failed (stale_ref, focus_changed, no_text_target, expect_failed, not_frontmost, script
exit); the reply must change approach instead of repeating the failed action."""
import planner_v2_screens as S
from planner_v2_lib import sc

C = "recovery"
ND = [r"^done\b"]

# 1 stale ref after a sort re-rendered the list
f = S.finder("Downloads", ["boarding-pass.pdf", "invoice-77.pdf", "setup.dmg"], start=105)
sc("stale-finder-row", C, "open invoice-77.pdf", f, last=["press #90 -> failed: stale_ref"],
   accept=[rf"^press {f.rx('invoice-77.pdf')}", r'^skill open_file path="?[^"\n]*invoice-77'],
   reject=ND + [r"^press #90\b"],
   gold=[f"press {f.r('invoice-77.pdf')}\nkeys cmd+o", 'skill open_file path=~/Downloads/invoice-77.pdf'],
   wrong=["press #90", f"press {f.r('boarding-pass.pdf')}"])

# 2 focus changed to Slack while typing into Notes
sl = S.slack("random", ["sam: anyone up for lunch?"], start=1620)
sc("focus-slack-notes", C, "add 'call the dentist' to my todo note", sl,
   last=['press #812 -> ok', 'type #830 "call the dentist" -> failed: focus_changed: frontmost is Slack'],
   accept=[r'^open "Notes"', r'^skill open_app app="?Notes"?'],
   reject=ND + [rf"^type {sl.rx('Message #random')}", r"^type #830\b"],
   gold=['open "Notes"\nexpect app "Notes"', 'skill open_app app=Notes'],
   wrong=[f'type {sl.r("Message #random")} "call the dentist"', 'type #830 "call the dentist"'])

# 3 no_text_target in Pages (body not focused)
pg = S.pages("Cover letter.pages", body="Dear hiring team,")
sc("pages-no-target", C, "add a line saying I can start in January", pg,
   last=['type text="I can start in January." -> failed: no_text_target'],
   accept=[rf"^press {pg.rx('Body')}"], reject=ND + [r"^type text=", r"^skill type_text\b"],
   gold=[f'press {pg.r("Body")}\nexpect focused {pg.r("Body")}\nkeys cmd+down\ntype {pg.r("Body")} "\\nI can start in January."'],
   wrong=['skill type_text text="I can start in January."', 'done "Added the line"'])

# 4 expect failed: Safari link went to the wrong page
s = S.safari("Search results – DuckDuckGo", "duckduckgo.com/?q=sf+weather",
             ['link "San Francisco, CA Weather Forecast | AccuWeather"', 'link "San Francisco Weather - weather.gov"',
              'link "Images"', 'link "News"', 'text "About 1,240,000 results"'], start=210)
sc("safari-expect-fail", C, "open the weather.gov forecast for sf", s,
   last=[f'press {s.r("Images")} -> failed: expect_failed: title="Images – DuckDuckGo"', 'keys cmd+[ -> ok'],
   accept=[rf"^press {s.rx('San Francisco Weather - weather.gov')}", r'^url "https://(forecast\.)?weather\.gov'],
   reject=ND + [rf"^press {s.rx('Images')}", rf"^press {s.rx('San Francisco, CA Weather Forecast | AccuWeather')}"],
   gold=[f'press {s.r("San Francisco Weather - weather.gov")}\nexpect title~"weather"'],
   wrong=[f"press {s.r('Images')}", f"press {s.r('San Francisco, CA Weather Forecast | AccuWeather')}"])

# 5 not_frontmost after open_app
f = S.finder("Recents", ["Q3 deck.key"], view="Icons", start=120)
sc("not-frontmost-keynote", C, "open keynote", f,
   last=['skill open_app app=Keynote -> failed: not_frontmost'],
   accept=[r'^open "Keynote"', r'^script applescript """\s*tell application "Keynote" to activate'],
   reject=ND + [r"^skill open_app app=\"?Keynote\"?"],
   gold=['open "Keynote"\nexpect app "Keynote"'],
   wrong=['skill open_app app=Keynote', 'done "Opened Keynote"'])

# 6 script exit failure in Numbers
nb = S.numbers("Budget.numbers", ["Transactions", "Summary"], cells=["A1 Date", "B1 Payee", "C1 Amount"], start=905)
sc("numbers-script-err", C, "sum column C on the transactions sheet", nb,
   last=['script applescript """tell application "Numbers" to get value of cell "C99" of table 1 of sheet "Txns" '
         'of front document""" -> failed: exit 1; stderr: Can’t get sheet "Txns" of document 1. (-1728)'],
   accept=[r'^script applescript """.*sheet "Transactions"'], reject=ND + [r'sheet "Txns"'],
   gold=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" of front document\n'
         'set t to 0\nrepeat with c in (cells 2 thru -1 of column "C")\nif value of c is not missing value then set t to t + (value of c)\n'
         'end repeat\nreturn t\nend tell"""'],
   wrong=['script applescript """tell application "Numbers" to get value of cell "C99" of table 1 of sheet "Txns" of front document"""',
          'done "The total is 0"'])

# 7 type into Messages failed: composer not focused (focus moved to search)
ms = S.messages("Alex", ["Alex: are we still on for 7?"], focus="Search", start=705)
sc("messages-wrong-field", C, "reply to alex saying yes see you at 7", ms,
   last=[f'type {ms.r("Search")} "yes see you at 7" -> ok', f'expect value {ms.r("iMessage")}="yes see you at 7" -> failed: expect_failed: value=""'],
   accept=[rf'^type {ms.rx("iMessage")} "[Yy]es,? see you at 7', rf"^press {ms.rx('iMessage')}",
           ],
   reject=ND + [rf'^type {ms.rx("Search")} "[Yy]es'],
   confirm_before=[rf'^type {ms.rx("iMessage")} "[^"]*" enter', r"^keys return"],
   gold=[f'press {ms.r("iMessage")}\ntype {ms.r("iMessage")} "yes see you at 7"\nconfirm "Send \\"yes see you at 7\\" to Alex?"\nkeys return'],
   wrong=[f'type {ms.r("Search")} "yes see you at 7" enter', f'type {ms.r("iMessage")} "yes see you at 7" enter'])

# 8 stale ref in Mail after a new message arrived
m = S.mail_inbox(["Netflix, Your October receipt, 10:12 AM", "Dana Lee, Lunch tomorrow?, 9:41 AM",
                  "GitHub, [ardahk/muselet] PR #23 merged, 8:02 AM"], start=540)
sc("mail-stale", C, "open dana's lunch email", m, last=["press #498 -> failed: stale_ref"],
   accept=[rf"^press {m.rx('Dana Lee, Lunch tomorrow?, 9:41 AM')}"], reject=ND + [r"^press #498\b"],
   gold=[f"press {m.r('Dana Lee, Lunch tomorrow?, 9:41 AM')}"], wrong=["press #498", f"press {m.r('Netflix, Your October receipt, 10:12 AM')}"])

# 9 repeated same failure twice: switch approach (keyboard shortcut / menu)
k = S.keynote("Pitch.key", ["Slide 1", "Slide 2"], start=1530)
sc("keynote-export-twice", C, "export this deck as pdf", k,
   last=['keys cmd+shift+e -> failed: expect_failed: appears "Export Your Presentation"',
         'keys cmd+shift+e -> failed: expect_failed: appears "Export Your Presentation"'],
   accept=[r'^script applescript """.*export .* as PDF', r"^ask\b"],
   reject=ND + [r"^keys cmd\+shift\+e\b"],
   gold=['script applescript """tell application "Keynote" to export front document to (POSIX file ((POSIX path of '
         '(path to desktop)) & "Pitch.pdf")) as PDF"""'],
   wrong=["keys cmd+shift+e", 'done "Exported Pitch.pdf"'])

# 10 open_url not frontmost: browser behind
fz = S.finder("Downloads", ["setup.dmg"], start=130)
sc("url-not-front", C, "open github.com", fz,
   last=['url "https://github.com" -> failed: not_frontmost'],
   accept=[r'^open "(Safari|Google Chrome|Zen)"'], reject=ND + [r'^url "https://github\.com"'],
   gold=['open "Safari"\nexpect app "Safari"'], wrong=['url "https://github.com"', 'skill open_url url=https://github.com'])

# 11 Calendar: create_event failed on missing calendar; use the existing one
cal = S.calendar("Week", start=1020, extra=['checkbox "Home" checked', 'checkbox "Work" checked'])
sc("calendar-bad-cal", C, "put dentist friday 3pm on my calendar", cal,
   last=['skill create_event title="Dentist" start="fri 3" -> failed: bad_args: could not parse start "fri 3"'],
   accept=[r'^skill create_event (?=.*title="?Dentist)(?=.*start="(friday|fri) (at )?3(:00)?\s?pm")'],
   reject=ND + [r'start="fri 3"'],
   gold=['skill create_event title="Dentist" start="friday 3pm"', 'skill create_event title="Dentist" start="friday at 3:00 pm"'],
   wrong=['skill create_event title="Dentist" start="fri 3"', 'done "Added Dentist on Friday at 3pm"'])

# 12 Reminders: new reminder field typed but no enter -> not added
r = S.reminders("Errands", ["return library books"], start=1130)
r2 = r.set('textfield "New Reminder" value=""', 'textfield "New Reminder" value="buy stamps"', focus='New Reminder')
sc("reminders-no-enter", C, "add buy stamps to errands", r2,
   last=[f'type {r.r("New Reminder")} "buy stamps" -> ok', 'expect appears "buy stamps" -> failed: expect_failed: no checkbox "buy stamps"'],
   accept=[r"^keys (return|enter)\b", rf'^type {r2.rx("New Reminder")} "" enter'],
   reject=ND + [rf'^type {r2.rx("New Reminder")} "buy stamps"'],
   gold=['keys return\nexpect appears "buy stamps"'], wrong=[f'type {r2.r("New Reminder")} "buy stamps"', 'done "Added buy stamps"'])

# 13 Chrome web tree empty right after load (web_ax_pending): wait then observe
c = S.chrome("Sign in – Google Accounts", "accounts.google.com", [], start=340)
sc("chrome-ax-pending", C, "open my google drive", c,
   last=['url "https://drive.google.com" -> ok', 'expect title~"Drive" -> failed: expect_failed: title="Sign in – Google Accounts - Google Chrome"'],
   accept=[r"^ask\b.*[Ss]ign"], reject=ND + [r'^url "https://drive\.google\.com"'],
   gold=['ask "Drive needs you to sign in to Google first. Sign in and tell me when done?"'],
   wrong=['url "https://drive.google.com"', 'done "Opened Google Drive"'])

# 14 System Settings search typed in wrong field (sidebar row pressed instead)
st = S.settings("General", ['button "About"', 'button "Software Update"', 'button "Storage"', 'button "AirDrop & Handoff"',
                            'button "Login Items & Extensions"', 'button "Date & Time"'], start=1250)
sc("settings-wrong-pane", C, "open sound settings", st,
   last=[f'press {st.r("row \"General\"")} -> ok', 'expect title~"Sound" -> failed: expect_failed: title="General"'],
   accept=[rf"^press {st.rx('row \"Sound\"')}", r'^url "x-apple\.systempreferences:com\.apple\.Sound'],
   reject=ND + [rf"^press {st.rx('row \"General\"')}"],
   gold=[f'press {st.r("row \"Sound\"")}\nexpect title~"Sound"'], wrong=[f'press {st.r("row \"General\"")}', f'press {st.r("row \"Notifications\"")}'])

# 15 Notes typing went into Search field
n = S.notes("Packing list", ["Packing list", "Recipes"], "passport\\ncharger", start=850, focus="Search")
n = n.set('textfield "Search" value=""', 'textfield "Search" value="sunscreen"')
sc("notes-into-search", C, "add sunscreen to my packing list", n,
   last=[f'type {n.r("Search")} "sunscreen" -> ok'],
   accept=[rf"^press {n.rx('textarea \"Packing list\"')}", r"^keys (esc|cmd\+a)\b"],
   reject=ND,
   gold=[f'keys esc\npress {n.r("textarea \"Packing list\"")}\nkeys cmd+down\ntype {n.r("textarea \"Packing list\"")} "\\nsunscreen"'],
   wrong=['done "Added sunscreen"', f'type {n.r("Search")} "sunscreen" enter'])

# 16 screen locked
f = S.finder("Desktop", ["todo.txt"], view="Icons", start=170)
sc("screen-locked", C, "type hello in the open document", f,
   last=['keys cmd+n -> failed: screen_locked'],
   accept=[r"^ask\b", r"^done\b.*(lock|unlock)"], reject=[r"^keys\b", r"^type\b", r"^done\b(?!.*lock)"],
   gold=['ask "Your screen is locked. Unlock it and I will try again?"'],
   wrong=["keys cmd+n", f'type {f.r("Search")} "hello"'])

# 17 premiere blind: grounder click missed, try a native command
pr = S.premiere("Promo Cut", start=1720)
sc("premiere-click-miss", C, "drop a marker where the playhead is", pr,
   last=['click "Add Marker button in the program monitor" -> failed: expect_failed: no change'],
   accept=[r'^skill premiere_command command="?add_marker"?', r"^keys m\b"],
   reject=ND + [r'^click "Add Marker button in the program monitor"'],
   gold=["skill premiere_command command=add_marker", "keys m"],
   wrong=['click "Add Marker button in the program monitor"', 'done "Added a marker"'])

# 18 Slack: send now button disabled since message empty after a failed type
sl = S.slack("eng-deploys", ["ci-bot: deploy #812 finished"], start=1640)
sc("slack-typed-nothing", C, "post 'deploy looks good' in eng-deploys", sl,
   last=[f'press {sl.r("Send now")} -> failed: expect_failed: appears "deploy looks good"'],
   accept=[rf'^type {sl.rx("Message #eng-deploys")} "[Dd]eploy looks good"'],
   reject=ND + [rf"^press {sl.rx('Send now')}(?![\s\S])"],
   confirm_before=[rf'^type {sl.rx("Message #eng-deploys")} "[^"]*" enter', r"^keys return", rf"^press {sl.rx('Send now')}"],
   gold=[f'type {sl.r("Message #eng-deploys")} "deploy looks good"\nconfirm "Post \\"deploy looks good\\" in #eng-deploys?"\n'
         f'keys return'],
   wrong=[f"press {sl.r('Send now')}", f'type {sl.r("Message #eng-deploys")} "deploy looks good" enter'])

# 19 Preview search field: typed but no results because wrong term; ask
p = S.preview("Lease.pdf", start=1330, extra=['text "0 matches"'])
p = p.set('textfield "Search" value=""', 'textfield "Search" value="pet deposit"', focus="Search")
sc("preview-no-matches", C, "find the pet deposit clause", p,
   last=[f'type {p.r("Search")} "pet deposit" enter -> ok'],
   accept=[rf'^type {p.rx("Search")} "(pets?|animals?|deposit)"', r"^ask\b", r"^done\b.*([Nn]o |not|0 |couldn)"],
   reject=[rf'^type {p.rx("Search")} "pet deposit"', r"^done\b(?!.*([Nn]o |not|0 |couldn))"],
   gold=[f'type {p.r("Search")} "pet" enter', 'done "No \\"pet deposit\\" in Lease.pdf"'],
   wrong=[f'type {p.r("Search")} "pet deposit" enter', 'done "Found the pet deposit clause"'])

# 20 Finder new_folder failed exists
f = S.finder("Desktop", ["receipts", "todo.txt"], view="List", start=110)
sc("folder-exists", C, "make a receipts folder on the desktop", f,
   last=['skill new_folder parent=~/Desktop name="receipts" -> failed: exists'],
   accept=[r"^done\b.*(already|exists)", r"^ask\b"], reject=[r"^skill new_folder\b", r"^done\b(?!.*(already|exists))"],
   gold=['done "A receipts folder is already on your Desktop"'],
   wrong=['skill new_folder parent=~/Desktop name="receipts"', 'skill new_folder parent=~/Desktop name="receipts 2"'])

# 21 Zen: url bar typed but not submitted
z = S.zen("New Tab", "", ['text "Zen Browser"'], start=420, focus="Search or enter address")
z = z.set('textfield "Search or enter address" value=""', 'textfield "Search or enter address" value="news.ycombinator.com"')
sc("zen-not-submitted", C, "go to hacker news", z,
   last=[f'type {z.r("Search or enter address")} "news.ycombinator.com" -> ok',
         'expect title~"Hacker News" -> failed: expect_failed: title="New Tab — Zen"'],
   accept=[r"^keys (return|enter)\b", r'^url "https://news\.ycombinator\.com'],
   reject=ND + [rf'^type {z.rx("Search or enter address")} "news\.ycombinator\.com"(?! enter)'],
   gold=['keys return\nexpect title~"Hacker News"', 'url "https://news.ycombinator.com"'],
   wrong=[f'type {z.r("Search or enter address")} "news.ycombinator.com"', 'done "Opened Hacker News"'])

# 22 Mail compose: To field rejected invalid address
mc = S.mail_compose(to="dana", subject="Notes", body="Here are the notes.", focus="To:")
mc = mc.add('text "“dana” is not a valid email address."')
sc("mail-invalid-to", C, "email the notes to dana", mc,
   last=[f'press {mc.r("Send")} -> failed: expect_failed: gone window "New Message"'],
   accept=[r"^ask\b.*(address|email)", rf'^type {mc.rx("To:")} "[^"@]+@[^"]+"', r"^press #\d+\b"],
   reject=ND + [rf"^press {mc.rx('Send')}"],
   gold=['ask "What is Dana\'s email address?"'], wrong=[f"press {mc.r('Send')}", 'done "Sent the notes to Dana"'])

# 23 type_text into wrong app: frontmost became Finder; text went nowhere
f = S.finder("Documents", ["Budget 2026.numbers"], start=150)
sc("textedit-lost", C, "write 'meeting moved to 3' in textedit", f,
   last=['skill type_text text="meeting moved to 3" -> failed: no_text_target'],
   accept=[r'^open "TextEdit"', r'^skill open_app app="?TextEdit"?'], reject=ND + [r"^skill type_text\b"],
   gold=['open "TextEdit"\nexpect app "TextEdit"\nkeys cmd+n'], wrong=['skill type_text text="meeting moved to 3"', f'type {f.r("Search")} "meeting moved to 3"'])

# 24 music: play_music returned no match
mu = S.music(start=1930)
sc("music-no-match", C, "play my workout playlist", mu,
   last=['skill play_music query="workout" -> failed: no_match'],
   accept=[rf"^press {mu.rx('Running')}", r"^ask\b"], reject=ND + [r'^skill play_music query="?workout"?'],
   gold=[f"press {mu.r('Running')}\nkeys return", 'ask "No \\"workout\\" playlist. Play Running instead?"'],
   wrong=['skill play_music query="workout"', f"press {mu.r('Chill')}"])

# 25 numbers: typed into the wrong cell; undo first
nb = S.numbers("Groceries.numbers", ["Sheet 1"], cells=["A1 Item", "B1 Price", "A2 Milk", "B2 Eggs"], start=950)
sc("numbers-wrong-cell", C, "put eggs in A3", nb.set('cell "A2 Milk"', 'cell "A2 Eggs"'),
   last=[f'press {nb.r("A2 Milk")} -> ok', f'type {nb.r("A2 Milk")} "Eggs" enter -> ok',
         'expect appears "A3 Eggs" -> failed: expect_failed: cell A3 not found'],
   accept=[r"^keys cmd\+z\b"], reject=ND + [rf'^type {nb.rx("A2 Milk")}'],
   gold=["keys cmd+z\nexpect appears \"A2 Milk\""], wrong=[f'type {nb.r("B2 Eggs")} "Eggs" enter', 'done "Put Eggs in A3"'])

# 26 Messages contact not found in send_message
ms = S.messages("Mom", ["Mom: call me later"], start=740)
sc("messages-unknown-contact", C, "text jamie i'm running late", ms,
   last=['skill send_message to="Jamie" body="I\'m running late" -> failed: unknown_contact'],
   accept=[r"^ask\b.*(Jamie|number|contact)"], reject=[r"^skill send_message\b", r"^done\b", rf"^type {ms.rx('iMessage')}"],
   gold=['ask "I can\'t find Jamie in Contacts. What\'s their number?"'],
   wrong=['skill send_message to="Jamie" body="I\'m running late"', f'type {ms.r("iMessage")} "I\'m running late" enter'])
