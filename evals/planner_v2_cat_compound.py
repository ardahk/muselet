"""compound: two or more sub-goals in one utterance; the first batch starts the right part and never ends with an
early `done`."""
import planner_v2_screens as S
from planner_v2_lib import sc

C = "compound"
ND = [r"^done\b"]
F0 = S.finder("Recents", ["Q3 deck.key"], view="Icons", start=100)

sc("dark-and-volume", C, "turn on dark mode and set volume to 30", F0,
   accept=[r'^skill dark_mode on="?true"?', r'^skill set_volume level="?30"?'], reject=ND + [r"level=\"?(3|300)\b"],
   gold=["skill dark_mode on=true\nskill set_volume level=30"], wrong=["skill dark_mode on=true\ndone \"Dark mode on\""])

sc("dark-done-volume-left", C, "turn on dark mode and set volume to 30", F0, last=["skill dark_mode on=true -> ok"],
   accept=[r'^skill set_volume level="?30"?'], reject=ND + [r"^skill dark_mode\b"],
   gold=["skill set_volume level=30"], wrong=['done "Dark mode on, volume 30"', "skill dark_mode on=true"])

sc("folder-then-open", C, "make a folder called taxes 2026 in documents and open it", F0,
   accept=[r'^skill new_folder (?=.*parent="?~/Documents"?)(?=.*name="[Tt]axes 2026")'], reject=ND,
   gold=['skill new_folder parent=~/Documents name="taxes 2026"\nskill open_folder path="~/Documents/taxes 2026"'],
   wrong=['skill open_folder path="~/Documents/taxes 2026"', 'skill new_folder parent=~/Documents name="taxes 2026"\ndone "Made it"'])

sc("timer-and-music", C, "start a 25 minute timer and play my chill playlist", F0,
   accept=[r'^skill start_timer duration="?25 ?min', r'^skill play_music query="?[Cc]hill'], reject=ND + [r'duration="?(5|2\.5|250)\b'],
   gold=['skill start_timer duration="25 minutes"\nskill play_music query="Chill"'], wrong=['skill start_timer duration="25 minutes"\ndone "Timer set"'])

m = S.mail_inbox(["Dana Lee, Lunch tomorrow?, 9:41 AM", "Spam Co, WIN NOW, 7:02 AM"], start=760)
sc("archive-then-open", C, "archive the spam co email then open dana's", m,
   accept=[rf"^press {m.rx('Spam Co, WIN NOW, 7:02 AM')}"], reject=ND + [rf"^press {m.rx('Move to Trash')}"],
   gold=[f"press {m.r('Spam Co, WIN NOW, 7:02 AM')}\npress {m.r('button "Archive"')}\npress {m.r('Dana Lee, Lunch tomorrow?, 9:41 AM')}"],
   wrong=[f"press {m.r('Dana Lee, Lunch tomorrow?, 9:41 AM')}", f"press {m.r('Spam Co, WIN NOW, 7:02 AM')}\npress {m.r('Move to Trash')}"])

sc("reminder-and-event", C, "remind me to buy flowers saturday 10am and put mom's birthday dinner sunday 7pm on my calendar", F0,
   accept=[r'^skill create_reminder (?=.*title="[^"]*flowers)', r'^skill create_event (?=.*title="[^"]*[Bb]irthday)(?=.*sunday 7\s?pm)'],
   reject=ND,
   gold=['skill create_reminder title="Buy flowers" due="saturday 10am"\nskill create_event title="Mom\'s birthday dinner" start="sunday 7pm"'],
   wrong=['skill create_reminder title="Buy flowers" due="saturday 10am"\ndone "Reminder set"', 'skill create_event title="Buy flowers" start="saturday 10am"\ndone "Done"'])

s = S.safari("Start Page", "", ['link "Favorites"'], start=440, url_value="")
sc("two-tabs", C, "open github and hacker news in two tabs", s,
   accept=[r'^url "https://(github\.com|news\.ycombinator\.com)'], reject=ND,
   gold=['url "https://github.com"\nkeys cmd+t\nurl "https://news.ycombinator.com"'], wrong=['url "https://github.com"\ndone "Opened both"'])

sc("brightness-wifi-off", C, "dim the screen to 40 and turn off wifi", F0,
   accept=[r'^skill set_brightness level="?40"?', r'^skill wifi on="?false"?'], reject=ND + [r'^skill wifi on="?true"?'],
   gold=["skill set_brightness level=40\nskill wifi on=false"], wrong=["skill set_brightness level=40\nskill wifi on=true"])

nb = S.numbers("Budget.numbers", ["Transactions", "Summary"], start=1080)
sc("numbers-total-then-chart", C, "total the amounts on transactions, then make a bar chart of it", nb,
   accept=[r'^script applescript """.*sheet "Transactions"'], reject=ND + [rf"^press {nb.rx('Chart')}(?![\s\S])"],
   gold=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" of front document\n'
         'set t to 0\nrepeat with c in (cells 2 thru -1 of column "C")\nif value of c is not missing value then set t to t + (value of c)\n'
         'end repeat\nreturn t\nend tell"""'],
   wrong=[f"press {nb.r('Chart')}", 'done "Total added and chart made"'])

ms = S.messages("Alex", ["Alex: running late?"], start=900)
sc("text-and-timer", C, "text alex i'll be 10 minutes late and set a 10 minute timer", ms,
   accept=[rf'^type {ms.rx("iMessage")} "[^"]*10 min', r"^confirm\b", r'^skill start_timer duration="?10 ?min'], reject=ND,
   confirm_before=[rf'^type {ms.rx("iMessage")} "[^"]*" enter', r"^keys return\b", r"^skill send_message\b"],
   gold=[f'type {ms.r("iMessage")} "I\'ll be 10 minutes late"\nconfirm "Send \\"I\'ll be 10 minutes late\\" to Alex?"\nkeys return\nskill start_timer duration="10 minutes"'],
   wrong=[f'type {ms.r("iMessage")} "I\'ll be 10 minutes late" enter\nskill start_timer duration="10 minutes"'])

sc("quit-and-lock", C, "quit slack and lock my screen", S.slack("general", start=1760),
   accept=[r'^skill quit_app app="?Slack"?', r"^keys cmd\+q\b"], reject=ND,
   gold=["skill quit_app app=Slack\nskill lock_screen"], wrong=["skill lock_screen", 'skill quit_app app=Slack\ndone "Quit Slack"'])

st = S.settings("Sound", ['slider "Output volume"', 'checkbox "Mute" unchecked', 'row "MacBook Pro Speakers" selected',
                          'row "AirPods Pro"', 'text "Output"'], start=1420)
sc("airpods-and-volume", C, "switch output to my airpods and put the volume at 50", st,
   accept=[rf"^press {st.rx('AirPods Pro')}"], reject=ND + [rf"^press {st.rx('MacBook Pro Speakers')}"],
   gold=[f"press {st.r('AirPods Pro')}\nskill set_volume level=50"], wrong=["skill set_volume level=50\ndone \"Volume 50\""])

sc("airpods-done-volume", C, "switch output to my airpods and put the volume at 50",
   st.set('row "MacBook Pro Speakers" selected', 'row "MacBook Pro Speakers"').set('row "AirPods Pro"', 'row "AirPods Pro" selected'),
   last=[f"press {st.r('AirPods Pro')} -> ok"], accept=[r'^skill set_volume level="?50"?', rf"^scroll {st.rx('Output volume')}"],
   reject=ND + [rf"^press {st.rx('AirPods Pro')}"], gold=["skill set_volume level=50"], wrong=['done "Switched to AirPods"'])

nt = S.notes("Recipes", ["Recipes", "Packing list"], "pancakes", start=980)
sc("note-then-type", C, "make a new note called ideas that says tbd", nt,
   accept=[rf"^press {nt.rx('New Note')}", r"^keys cmd\+n\b", r'^skill new_note (?=.*title="?[Ii]deas)'], reject=ND + [rf"^press {nt.rx('Delete')}"],
   gold=['skill new_note title="Ideas" body="tbd"', f"press {nt.r('New Note')}"],
   wrong=[f"press {nt.r('Delete')}", 'skill new_note title="Ideas" body="tbd"\ndone "Made the Ideas note"'])

sc("screenshot-and-mail", C, "take a screenshot of this window and email it to dana@acme.com", S.chrome("Dashboard", "grafana.acme.com", ['text "p95 412 ms"'], start=670),
   accept=[r'^skill take_screenshot (region="?window"?)?'], reject=ND, confirm_before=[r"^skill compose_email\b"],
   gold=['skill take_screenshot region=window'], wrong=['skill compose_email to="dana@acme.com" subject="Screenshot" body="See attached"'])

sc("hide-and-layout", C, "hide finder and put safari on the left half", F0,
   accept=[r'^skill hide_app app="?Finder"?', r'^open "Safari"', r'^skill open_app app="?Safari"?'], reject=ND + [r"layout=\"?right"],
   gold=["skill hide_app app=Finder\nopen \"Safari\"\nskill window_layout layout=left"], wrong=["skill window_layout layout=right"])

r = S.reminders("Errands", ["return library books", "buy stamps"], start=1200)
sc("check-two", C, "check off library books and stamps", r,
   accept=[rf"^press {r.rx('return library books')}", rf"^press {r.rx('buy stamps')}"], reject=ND,
   gold=[f"press {r.r('return library books')}\npress {r.r('buy stamps')}"], wrong=[f"press {r.r('return library books')}\ndone \"Checked off\""])

sc("check-two-half", C, "check off library books and stamps", r.set('checkbox "return library books" unchecked', 'checkbox "return library books" checked'),
   last=[f"press {r.r('return library books')} -> ok"], accept=[rf"^press {r.rx('buy stamps')}"],
   reject=ND + [rf"^press {r.rx('return library books')}"], gold=[f"press {r.r('buy stamps')}"], wrong=[f"press {r.r('return library books')}"])

c = S.chrome("Inbox (3) - arda@gmail.com - Gmail", "mail.google.com/mail/u/0/#inbox", ['row "GitHub [ardahk/muselet] CI failed"',
             'row "Mom Sunday?"', 'button "Compose"', 'button "Archive"', 'button "Mark as read"'], start=690)
sc("gmail-read-archive", C, "open the github email and then archive it", c, accept=[rf"^press {c.rx('row \"GitHub [ardahk/muselet] CI failed\"')}"],
   reject=ND + [rf"^press {c.rx('row \"Mom Sunday?\"')}"], gold=[f"press {c.r('row \"GitHub [ardahk/muselet] CI failed\"')}\npress {c.r('Archive')}"],
   wrong=[f"press {c.r('Archive')}", f"press {c.r('row \"Mom Sunday?\"')}"])

k = S.keynote("Pitch.key", ["Slide 1", "Slide 2"], start=1680)
sc("keynote-add-and-play", C, "add a slide at the end and then start the show", k,
   accept=[rf"^press {k.rx('Slide 2')}", rf"^press {k.rx('Add Slide')}"], reject=ND,
   gold=[f"press {k.r('Slide 2')}\npress {k.r('Add Slide')}\npress {k.r('Play')}"], wrong=[f"press {k.r('Play')}"])

sc("open-and-search", C, "open safari and search for cheap flights to tokyo", F0,
   accept=[r'^skill web_search query="[^"]*[Tt]okyo', r'^open "Safari"', r'^url "https://[^"]*tokyo'], reject=ND,
   gold=['skill web_search query="cheap flights to Tokyo"', 'open "Safari"\nurl "https://www.google.com/search?q=cheap+flights+to+tokyo"'],
   wrong=['open "Safari"\ndone "Opened Safari"'])

pg = S.pages("Report.pages", body="Q3 summary", start=1500, focus="Body")
sc("pages-type-save", C, "add 'Revenue grew 12%.' and save", pg,
   accept=[r"^keys cmd\+down\b", rf'^type {pg.rx("Body")} "[^"]*Revenue grew 12%'], reject=ND + [r"21%"],
   gold=[f'keys cmd+down\ntype {pg.r("Body")} "\\nRevenue grew 12%."\nkeys cmd+s'], wrong=['keys cmd+s\ndone "Saved"'])

cal = S.calendar("Week", start=1160)
sc("agenda-and-mute", C, "mute the mac and tell me what's on today", cal,
   accept=[r'^skill mute on="?true"?', r"^skill todays_agenda\b"], reject=ND + [r'^skill mute on="?false"?'],
   gold=["skill mute on=true\nskill todays_agenda"], wrong=["skill mute on=false\nskill todays_agenda"])

sc("move-and-trash", C, "move setup.dmg to the trash and empty it", S.finder("Downloads", ["setup.dmg"], start=220),
   accept=[r"^confirm\b"], reject=ND, confirm_before=[r"^skill (move_to_trash|empty_trash)\b"],
   gold=['confirm "Trash setup.dmg and permanently empty the Trash?"\nskill move_to_trash path=~/Downloads/setup.dmg\nskill empty_trash'],
   wrong=["skill move_to_trash path=~/Downloads/setup.dmg\nskill empty_trash"])

z = S.zen("YouTube", "youtube.com", ['textfield "Search" value=""', 'button "Search"', 'text "Recommended"'], start=700)
sc("yt-search-fullscreen", C, "search youtube for lofi beats and make the window full screen", z,
   accept=[rf'^type {z.rx('textfield "Search"')} "[Ll]o-?fi beats"', r'^skill window_layout layout="?full"?'], reject=ND,
   gold=[f'type {z.r('textfield "Search"')} "lofi beats" enter\nskill window_layout layout=full'], wrong=[f'type {z.r("Search or enter address")} "lofi beats" enter'])

sc("copy-and-paste-note", C, "copy the selected text and paste it into a new note", S.safari("Recipe: Banana bread", "bakeit.example/banana-bread",
   ['button "Jump to recipe"', 'text "3 ripe bananas, 1/3 cup butter, 1 cup sugar"'], start=470),
   accept=[r"^skill copy_selection\b", r"^keys cmd\+c\b"], reject=ND + [r"^skill new_note\b(?=.*body=\"\")"],
   gold=['skill copy_selection\nskill open_app app=Notes\nkeys cmd+n\nkeys cmd+v', 'keys cmd+c\nopen "Notes"\nkeys cmd+n\nkeys cmd+v'],
   wrong=['open "Notes"\nkeys cmd+n\nkeys cmd+v', 'skill copy_selection\ndone "Copied"'])
