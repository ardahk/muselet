"""single_step: one obvious next action on a realistic screen."""
import planner_v2_screens as S
from planner_v2_lib import q, sc

C = "single_step"
NOT_DONE = [r"^done\b"]

f = S.finder("Documents", ["Budget 2026.numbers", "Lease.pdf", "Notes from call.txt"], view="Icons", start=140)
sc("finder-list", C, "switch this window to list view", f,
   accept=[rf"^press {f.rx('List')}", r"^keys cmd\+2\b"], reject=NOT_DONE + [rf"^press {f.rx('Columns')}"],
   gold=[f"press {f.r('List')}", "keys cmd+2"], wrong=[f"press {f.r('Columns')}", 'done "Switched to list view"'])

f = S.finder("Downloads", ["boarding-pass.pdf", "IMG_0912.HEIC", "setup.dmg"], view="List", start=161)
sc("finder-sort-date", C, "sort these by date modified", f,
   accept=[rf"^press {f.rx('Date Modified')}"], reject=NOT_DONE + [rf"^press {f.rx('Name')}"],
   gold=[f"press {f.r('Date Modified')}"], wrong=[f"press {f.r('Size')}"])

f = S.finder("Recents", ["Q3 deck.key", "invoice-77.pdf"], view="Icons", start=181)
sc("finder-go-desktop", C, "go to my desktop folder", f,
   accept=[rf"^press {f.rx('Desktop')}", r'^skill open_folder path="?(~/)?[Dd]esktop"?\s*$', r"^keys cmd\+shift\+d\b"],
   reject=NOT_DONE + [rf"^press {f.rx('Documents')}"],
   gold=[f"press {f.r('Desktop')}\nexpect title~\"Desktop\"", "skill open_folder path=~/Desktop"],
   wrong=["skill open_folder path=~/Documents", f"press {f.r('Downloads')}"])

s = S.safari("Apple", "apple.com", ['link "Store"', 'link "Mac"', 'link "iPad"', 'link "iPhone"', 'link "Support"',
                                    'button "Search apple.com"', 'text "iPhone 18 Pro. Built for Apple Intelligence."'],
             start=230)
sc("safari-support-link", C, "open apple support", s,
   accept=[rf"^press {s.rx('Support')}", r'^url "https://(www\.)?(support\.apple\.com|apple\.com/support)'],
   reject=NOT_DONE + [rf"^press {s.rx('Store')}"],
   gold=[f"press {s.r('Support')}\nexpect title~\"Support\""], wrong=[f"press {s.r('Store')}"])

s = S.safari("Start Page", "", ['link "Favorites"', 'link "GitHub"', 'link "Hacker News"', 'link "Wikipedia"'],
             start=250, url_value="")
sc("safari-new-tab", C, "open a new tab", s,
   accept=[rf"^press {s.rx('New Tab')}", r"^keys cmd\+t\b"], reject=NOT_DONE,
   gold=["keys cmd+t", f"press {s.r('New Tab')}"], wrong=['done "Opened a new tab"', "keys cmd+n"])

c = S.chrome("Pull requests · ardahk/muselet", "github.com/ardahk/muselet/pulls",
             ['link "Code"', 'link "Issues"', 'link "Pull requests"', 'link "Actions"', 'link "Wiki"',
              'link "Planner bench v2"', 'link "Speed lab results"', 'textfield "Search all pull requests" value="is:pr is:open"',
              'text "2 Open"'], start=330)
sc("chrome-reload", C, "reload this page", c,
   accept=[rf"^press {c.rx('Reload')}", r"^keys cmd\+r\b"], reject=NOT_DONE,
   gold=["keys cmd+r", f"press {c.r('Reload')}"], wrong=[f"press {c.r('Back')}"])

sc("chrome-issues", C, "show the issues tab of this repo", c,
   accept=[rf"^press {c.rx('Issues')}", r'^url "https://github\.com/ardahk/muselet/issues"'],
   reject=NOT_DONE + [rf"^press {c.rx('Pull requests')}"],
   gold=[f"press {c.r('Issues')}\nexpect title~\"Issues\""], wrong=[f"press {c.r('Pull requests')}"])

z = S.zen("Wikipedia, the free encyclopedia", "wikipedia.org",
          ['textfield "Search Wikipedia" value=""', 'button "Search"', 'link "English"', 'link "Español"',
           'link "Deutsch"', 'text "The Free Encyclopedia"'], start=410)
sc("zen-wiki-search", C, "search wikipedia for alan turing", z,
   accept=[rf'^type {z.rx("Search Wikipedia")} "[Aa]lan [Tt]uring"'], reject=NOT_DONE + [r"^url\b"],
   gold=[f'type {z.r("Search Wikipedia")} "alan turing" enter\nexpect title~"Turing"'],
   wrong=[f'type {z.r("Search or enter address")} "alan turing" enter', 'url "https://www.google.com/search?q=alan+turing"'])

m = S.mail_inbox(["Dana Lee, Lunch tomorrow?, 9:41 AM", "GitHub, [ardahk/muselet] PR #23 merged, 8:02 AM",
                  "Delta, Your trip to Seattle, Yesterday"], start=520)
sc("mail-compose", C, "start a new email", m,
   accept=[rf"^press {m.rx('Compose new message')}", r"^keys cmd\+n\b"], reject=NOT_DONE,
   gold=[f"press {m.r('Compose new message')}\nexpect appears \"To:\"", "keys cmd+n"],
   wrong=[f"press {m.r('Reply')}"])

sc("mail-open-trip", C, "open the delta email", m,
   accept=[rf"^press {m.rx('Delta, Your trip to Seattle, Yesterday')}"], reject=NOT_DONE + [r"^press .*Trash"],
   gold=[f"press {m.r('Delta, Your trip to Seattle, Yesterday')}"],
   wrong=[f"press {m.r('Dana Lee, Lunch tomorrow?, 9:41 AM')}"])

n = S.notes("Grocery list", ["Grocery list", "Trip ideas", "Book recs"], "eggs\\nmilk", start=820)
sc("notes-open-trip", C, "open my trip ideas note", n,
   accept=[rf"^press {n.rx('row \"Trip ideas\"')}"], reject=NOT_DONE + [rf"^press {n.rx('Delete')}"],
   gold=[f"press {n.r('row \"Trip ideas\"')}"], wrong=[f"press {n.r('row \"Book recs\"')}", f"press {n.r('Delete')}"])

cal = S.calendar("Week", start=1010)
sc("calendar-month", C, "show the whole month", cal,
   accept=[rf"^press {cal.rx('Month')}", r"^keys cmd\+3\b"], reject=NOT_DONE + [rf"^press {cal.rx('Year')}"],
   gold=[f"press {cal.r('Month')}", "keys cmd+3"], wrong=[f"press {cal.r('Year')}"])

sc("calendar-next-week", C, "go to next week", cal,
   accept=[rf"^press {cal.rx('Next')}"], reject=NOT_DONE + [rf"^press {cal.rx('Previous')}"],
   gold=[f"press {cal.r('Next')}"], wrong=[f"press {cal.r('Previous')}"])

r = S.reminders("Errands", ["return library books", "pick up prescription", "buy birthday card"], start=1120)
sc("reminders-check", C, "check off pick up prescription", r,
   accept=[rf"^press {r.rx('pick up prescription')}"], reject=[rf"^press {r.rx('return library books')}",
                                                               rf"^press {r.rx('buy birthday card')}"],
   gold=[f"press {r.r('pick up prescription')}"], wrong=[f"press {r.r('buy birthday card')}"])

st = S.settings("Bluetooth", ['checkbox "Bluetooth" unchecked', 'button "Advanced…"',
                              'text "This Mac is discoverable as “Arda’s MacBook Pro”."'],
                start=1210)
sc("settings-bt-on", C, "turn on bluetooth", st,
   accept=[rf"^press {st.rx('checkbox \"Bluetooth\"')}", r'^skill bluetooth on="?(true|on)"?'],
   reject=NOT_DONE + [rf"^press {st.rx('row \"Bluetooth\"')}", r"^skill bluetooth on=\"?(false|off)"],
   gold=[f"press {st.r('checkbox \"Bluetooth\"')}", "skill bluetooth on=true"],
   wrong=[f"press {st.r('row \"Bluetooth\"')}", "skill bluetooth on=false"])

st = S.settings("Appearance", ['radio "Auto" unchecked', 'radio "Light" checked', 'radio "Dark" unchecked',
                               'popup "Accent color"', 'popup "Highlight color"', 'popup "Show scroll bars"'],
                start=1240)
sc("settings-dark", C, "switch to dark appearance", st,
   accept=[rf"^press {st.rx('Dark')}", r'^skill dark_mode on="?(true|on)"?'],
   reject=NOT_DONE + [rf"^press {st.rx('Auto')}", r"^skill dark_mode on=\"?(false|off)"],
   gold=["skill dark_mode on=true", f"press {st.r('Dark')}"], wrong=[f"press {st.r('Auto')}"])

p = S.preview("Lease.pdf", start=1310)
sc("preview-rotate", C, "rotate this pdf", p,
   accept=[rf"^press {p.rx('Rotate')}", r"^keys cmd\+(r|l)\b"], reject=NOT_DONE + [rf"^press {p.rx('Markup')}"],
   gold=[f"press {p.r('Rotate')}", "keys cmd+r"], wrong=[f"press {p.r('Markup')}"])

k = S.keynote("Pitch.key", ["Slide 1", "Slide 2", "Slide 3"], start=1510)
sc("keynote-play", C, "start the slideshow", k,
   accept=[rf"^press {k.rx('Play')}", r"^keys cmd\+(alt|opt|option)\+p\b"], reject=NOT_DONE + [rf"^press {k.rx('Add Slide')}"],
   gold=[f"press {k.r('Play')}"], wrong=[f"press {k.r('Add Slide')}"])

sc("keynote-add-slide", C, "add a slide", k,
   accept=[rf"^press {k.rx('Add Slide')}", r"^keys cmd\+shift\+n\b"], reject=NOT_DONE + [rf"^press {k.rx('Play')}"],
   gold=[f"press {k.r('Add Slide')}"], wrong=[f"press {k.r('Play')}"])

sl = S.slack("general", ["dana: standup moved to 10", "sam: 👍"], start=1610)
sc("slack-open-design", C, "open the design channel", sl,
   accept=[rf"^press {sl.rx('row \"design\"')}"], reject=NOT_DONE + [rf"^type {sl.rx('Message #general')}"],
   gold=[f"press {sl.r('row \"design\"')}\nexpect title~\"design\""], wrong=[f"press {sl.r('row \"random\"')}"])

pr = S.premiere()
sc("premiere-razor", C, "cut the clip at the playhead", pr,
   accept=[r'^skill premiere_command command="?razor_at_playhead"?', r"^keys cmd\+k\b"],
   reject=NOT_DONE + [r"^press #170[1-3]\b"],
   gold=["skill premiere_command command=razor_at_playhead", "keys cmd+k"],
   wrong=["press #1701", "skill premiere_command command=add_marker"])

sc("premiere-start", C, "jump to the start of the sequence", pr,
   accept=[r'^skill premiere_command command="?go_to_start"?', r"^keys home\b"], reject=NOT_DONE,
   gold=["skill premiere_command command=go_to_start"], wrong=["skill premiere_command command=go_to_end"])

mu = S.music(start=1910)
sc("music-chill", C, "play my chill playlist", mu,
   accept=[r'^skill play_music query="?[Cc]hill', rf"^press {mu.rx('Chill')}"],
   reject=NOT_DONE + [rf"^press {mu.rx('Running')}"],
   gold=['skill play_music query="Chill"', f"press {mu.r('Chill')}"], wrong=[f"press {mu.r('Running')}"])

f = S.finder("Desktop", ["Screenshot 2026-10-23 at 4.12.55 PM.png", "todo.txt"], view="Icons", start=190)
sc("finder-search", C, "find my passport scan", f,
   accept=[r'^skill find_file query="[^"]*passport', rf'^type {f.rx("Search")} "[^"]*passport'],
   reject=NOT_DONE,
   gold=['skill find_file query="passport scan"', f'type {f.r("Search")} "passport" enter'],
   wrong=['skill find_file query="scan"', 'done "No passport scan on the desktop"'])

tx = S.textedit_doc("Dear landlord,", window="letter.txt", start=1810)
sc("textedit-bold", C, "make the text bold", tx,
   accept=[rf"^press {tx.rx('Bold')}", r"^keys cmd\+b\b", r"^keys cmd\+a\b"], reject=NOT_DONE + [rf"^press {tx.rx('Italic')}"],
   gold=["keys cmd+a\nkeys cmd+b"], wrong=[f"press {tx.r('Italic')}"])

nb = S.numbers("Budget.numbers", ["Transactions", "Summary"], start=930)
sc("numbers-sheet", C, "go to the summary sheet", nb,
   accept=[rf"^press {nb.rx('Summary')}"], reject=NOT_DONE + [rf"^press {nb.rx('Add Sheet')}"],
   gold=[f"press {nb.r('Summary')}"], wrong=[f"press {nb.r('Add Sheet')}"])
