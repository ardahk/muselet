"""done_gating: `done` exactly when the observation / last batch proves the goal, never before."""
import planner_v2_screens as S
from planner_v2_lib import sc

C = "done_gating"
DONE = [r"^done\b"]

# ---- proven: done is the only right move (wrong = redo the action) ----
f = S.finder("Desktop", ["receipts", "todo.txt"], start=110, view="List")
sc("folder-made", C, "make a folder called receipts on my desktop", f,
   last=['skill new_folder parent=~/Desktop name="receipts" -> ok'],
   accept=DONE, reject=[r"^skill new_folder\b", r"^keys cmd\+shift\+n\b"],
   gold=['done "Made receipts on your Desktop"'], wrong=['skill new_folder parent=~/Desktop name="receipts"', "keys cmd+shift+n"])

st = S.settings("Bluetooth", ['checkbox "Bluetooth" checked', 'button "Advanced…"', 'text "Nearby Devices"'], start=1260)
sc("bt-on-proven", C, "switch bluetooth on", st, last=[f'press {st.r("checkbox \"Bluetooth\"")} -> ok'],
   accept=DONE, reject=[rf"^press {st.rx('checkbox \"Bluetooth\"')}", r"^skill bluetooth\b"],
   gold=['done "Bluetooth is on"'], wrong=[f"press {st.r('checkbox \"Bluetooth\"')}", "skill bluetooth on=true"])

r = S.reminders("Errands", ["return library books", "buy stamps"], start=1140)
sc("reminder-added", C, "put buy stamps on my errands list", r,
   last=[f'type {r.r("New Reminder")} "buy stamps" enter -> ok', 'expect appears "buy stamps" -> ok'],
   accept=DONE, reject=[r"^type\b", r"^skill create_reminder\b"],
   gold=['done "Added buy stamps to Errands"'], wrong=[f'type {r.r("New Reminder")} "buy stamps" enter', 'skill create_reminder title="buy stamps"'])

s = S.safari("GitHub · Build and ship software", "github.com", ['link "Sign in"', 'link "Sign up"', 'link "Product"',
             'link "Pricing"', 'text "Build and ship software on a single, collaborative platform"'], start=240)
sc("safari-url-proven", C, "open github.com", s, last=['url "https://github.com" -> ok', 'expect title~"GitHub" -> ok'],
   accept=DONE, reject=[r"^url\b", r"^skill open_url\b", rf"^press {s.rx('Sign in')}"],
   gold=['done "Opened GitHub"'], wrong=['url "https://github.com"', f"press {s.r('Sign in')}"])

sc("script-total", C, "total up the amounts column for me", S.numbers("Budget.numbers", ["Transactions"], start=960),
   last=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" of front document…""" -> ok'],
   script_output="1287.4", accept=[r"^done\b.*1,?287\.40?\b"], reject=[r"^script\b", r"^done\b(?!.*1,?287\.4)"],
   gold=['done "The total is 1,287.40"'], wrong=['done "The total is 1,287"', 'script applescript """tell application "Numbers" to get value of cell "C2" of table 1 of sheet "Transactions" of front document"""'])

ms = S.messages("Mom", ["Mom: call me later", "You: On my way home", "Delivered"], start=760)
sc("message-delivered", C, "text mom on my way home", ms,
   last=['confirm "Send \\"On my way home\\" to Mom?" -> yes', f'type {ms.r("iMessage")} "On my way home" enter -> ok'],
   accept=DONE, reject=[r"^type\b", r"^skill send_message\b", r"^keys return\b"],
   gold=['done "Sent to Mom"'], wrong=[f'type {ms.r("iMessage")} "On my way home" enter', 'skill send_message to="Mom" body="On my way home"'])

cal = S.calendar("Day", start=1030, extra=['button "Dentist, 3:00 PM to 4:00 PM"', 'text "Friday, October 30"'])
sc("event-created", C, "put dentist friday 3pm on my calendar", cal,
   last=['skill create_event title="Dentist" start="friday 3pm" -> ok'],
   accept=DONE, reject=[r"^skill create_event\b", rf"^press {cal.rx('Add')}"],
   gold=['done "Dentist added Friday 3 PM"'], wrong=['skill create_event title="Dentist" start="friday 3pm"', f"press {cal.r('Add')}"])

tx = S.textedit_doc("hello from muselet", window="Untitled")
sc("textedit-typed", C, "write hello from muselet in a new textedit doc", tx,
   last=["keys cmd+n -> ok", f'type {tx.r("Text")} "hello from muselet" -> ok', f'expect value {tx.r("Text")}="hello from muselet" -> ok'],
   accept=DONE, reject=[r"^type\b", r"^keys cmd\+s\b", r"^keys cmd\+n\b"],
   gold=['done "Wrote it in a new TextEdit doc"'], wrong=[f'type {tx.r("Text")} "hello from muselet"', "keys cmd+s"])

st = S.settings("Appearance", ['radio "Auto" unchecked', 'radio "Light" unchecked', 'radio "Dark" checked',
                               'popup "Accent color"'], start=1280)
sc("dark-proven", C, "dark mode please", st, last=["skill dark_mode on=true -> ok"],
   accept=DONE, reject=[r"^skill dark_mode\b", rf"^press {st.rx('Dark')}"],
   gold=['done "Dark mode is on"'], wrong=["skill dark_mode on=true", f"press {st.r('Dark')}"])

sc("battery-answer", C, "how much battery do i have", S.finder("Recents", ["Q3 deck.key"], view="Icons", start=100),
   last=["skill battery_status -> ok"], script_output='{"percent": 64, "charging": false, "time_remaining": "4:12"}',
   accept=[r"^done\b.*64\s?%"], reject=[r"^skill battery_status\b", r"^done\b(?!.*64)"],
   gold=['done "64%, about 4 hours left"'], wrong=["skill battery_status", 'done "Battery is fine"'])

# ---- not proven yet: done is wrong (wrong = premature done) ----
mc = S.mail_compose(to="dana@acme.com", subject="Lunch", body="Thursday works for me.", focus="Message Body")
sc("mail-not-sent", C, "email dana that thursday works", mc,
   last=[f'type {mc.r("To:")} "dana@acme.com" -> ok', f'type {mc.r("Subject:")} "Lunch" -> ok',
         f'type {mc.r("Message Body")} "Thursday works for me." -> ok'],
   accept=[r"^confirm\b"], reject=DONE, confirm_before=[rf"^press {mc.rx('Send')}", r"^keys cmd\+shift\+d\b"],
   gold=[f'confirm "Send \\"Lunch\\" to dana@acme.com?"\npress {mc.r("Send")}\nexpect gone {mc.r("Send")}'],
   wrong=['done "Emailed Dana"', f'press {mc.r("Send")}'])

f = S.finder("Downloads", ["boarding-pass.pdf", "invoice-77.pdf"], start=125)
sc("folder-not-visible", C, "make a folder called taxes in downloads", f,
   last=["keys cmd+shift+n -> ok"],
   accept=[r'^skill new_folder parent="?~/Downloads"? name="?taxes"?', r"^ask\b"],
   reject=DONE, gold=['skill new_folder parent=~/Downloads name="taxes"'], wrong=['done "Made the taxes folder"'])

s = S.safari("Untitled", "", [], start=260, url_value="")
sc("safari-blank", C, "open the nytimes", s,
   last=['url "https://www.nytimes.com" -> ok', 'expect title~"New York Times" -> failed: expect_failed: title="Untitled"'],
   accept=[r"^wait \d+", r'^url "https://(www\.)?nytimes\.com', rf"^press {s.rx('Reload this page')}"], reject=DONE,
   gold=['wait 1500\nexpect title~"New York Times"', 'url "https://www.nytimes.com"'], wrong=['done "Opened the New York Times"'])

n = S.notes("Packing list", ["Packing list", "Recipes"], "passport\\ncharger", start=870)
sc("notes-text-missing", C, "put sunscreen on the packing list note", n,
   last=[f'press {n.r("textarea \"Packing list\"")} -> ok', 'type text="sunscreen" -> ok'],
   accept=[rf"^press {n.rx('textarea \"Packing list\"')}", rf'^type {n.rx("textarea \"Packing list\"")} "[^"]*sunscreen'],
   reject=DONE, gold=[f'type {n.r("textarea \"Packing list\"")} "\\nsunscreen"'], wrong=['done "Added sunscreen"'])

pr = S.premiere("Wedding Edit", start=1740)
sc("premiere-export-unverified", C, "export the sequence as h.264", pr,
   last=["keys cmd+m -> ok"],
   accept=[r'^click "[^"]*[Ee]xport'], reject=DONE,
   gold=['click "Export button in the Export window"'], wrong=['done "Exported the sequence"'])

sl = S.slack("general", ["dana: standup moved to 10"], draft="sounds good", start=1660)
sc("slack-draft-only", C, "reply sounds good in general", sl,
   last=[f'type {sl.r("Message #general")} "sounds good" -> ok'],
   accept=[r"^confirm\b"], reject=DONE, confirm_before=[r"^keys return\b", rf"^press {sl.rx('Send now')}"],
   gold=['confirm "Post \\"sounds good\\" in #general?"\nkeys return'], wrong=['done "Replied in #general"', "keys return"])

cal = S.calendar("Week", start=1050)
sc("event-no-proof", C, "add yoga saturday 9am", cal,
   last=[f"press {cal.r('Add')} -> ok"],
   accept=[r'^skill create_event (?=.*title="?[Yy]oga)(?=.*saturday 9\s?am)'], reject=DONE,
   gold=['skill create_event title="Yoga" start="saturday 9am"'], wrong=['done "Added yoga Saturday 9 AM"'])

st = S.settings("Wi‑Fi", ['checkbox "Wi‑Fi" unchecked', 'button "Other…"', 'text "Wi‑Fi is turned off"'], start=1300)
sc("wifi-still-off", C, "turn wifi on", st, last=["skill wifi on=true -> ok"],
   accept=[rf"^press {st.rx('checkbox \"Wi‑Fi\"')}", r"^ask\b"], reject=DONE,
   gold=[f"press {st.r('checkbox \"Wi‑Fi\"')}\nexpect appears \"Known Networks\""], wrong=['done "Wi-Fi is on"'])

z = S.zen("Checkout – Acme Store", "acme.store/checkout", ['textfield "Card number" value=""',
          'button "Place order"', 'text "Total $48.20"'], start=440)
sc("checkout-not-placed", C, "buy the cart on acme store", z, last=[],
   accept=[r"^ask\b.*[Cc]ard", r"^confirm\b"], reject=DONE + [rf"^type {z.rx('Card number')} \"\d"],
   confirm_before=[rf"^press {z.rx('Place order')}"],
   gold=['ask "What card should I use? I won\'t enter card numbers myself."'], wrong=['done "Bought the cart"', f"press {z.r('Place order')}"])

pg = S.pages("Report.pages", body="Q3 summary", start=1420)
sc("pages-save-unproven", C, "save this as report final", pg,
   last=["keys cmd+shift+s -> ok"],
   accept=[r"^wait \d+"], reject=DONE,
   gold=['wait 800\nexpect appears "Save As:"'], wrong=['done "Saved as Report final"'])

c = S.chrome("ardahk/muselet: on-device agent", "github.com/ardahk/muselet",
             ['button "Star"', 'button "Fork"', 'link "Issues"', 'text "Star 12"'], start=360)
sc("chrome-star", C, "star this repo", c, last=[],
   accept=[rf"^press {c.rx('Star')}"], reject=DONE, gold=[f"press {c.r('Star')}\nexpect appears \"Starred\""],
   wrong=['done "Starred the repo"', f"press {c.r('Fork')}"])

sc("starred-proven", C, "give this repo a star", c.set('button "Star"', 'button "Starred"').set('text "Star 12"', 'text "Starred 13"'),
   last=[f'press {c.r("Star")} -> ok', 'expect appears "Starred" -> ok'],
   accept=DONE, reject=[rf"^press #\d+"], gold=['done "Starred ardahk/muselet"'], wrong=[f"press {c.r('Star')}"])

m = S.mail_inbox(["Delta, Your trip to Seattle, Yesterday"], start=580)
sc("mail-search-zero", C, "find the email from the landlord", m.set('textfield "Search" value=""',
   'textfield "Search" value="landlord"').add('text "No Results"'),
   last=[f'type {m.r("Search")} "landlord" enter -> ok'],
   accept=[r"^ask\b", r"^done\b.*([Nn]o |n't|not)"], reject=[r"^done\b(?!.*([Nn]o |n't|not))"],
   gold=['ask "No mail matches \\"landlord\\". What\'s their name or email?"', 'done "No emails match landlord"'],
   wrong=['done "Found the landlord email"'])

k = S.keynote("Pitch.key", ["Slide 1", "Slide 2", "Slide 3"], start=1560)
sc("keynote-slide-added", C, "add another slide to the deck", k, last=[f'press {k.r("Add Slide")} -> ok', 'expect appears "Slide 3" -> ok'],
   accept=DONE, reject=[rf"^press {k.rx('Add Slide')}", r"^keys cmd\+shift\+n\b"],
   gold=['done "Added Slide 3"'], wrong=[f"press {k.r('Add Slide')}"])

p = S.preview("Scan 12.pdf", start=1350)
sc("preview-saved-unknown", C, "export this pdf as a jpeg", p, last=[],
   accept=[r'^script (applescript|shell|jxa) """.*(sips|JPEG|jpe?g)', r"^ask\b"], reject=DONE,
   gold=['script applescript """set p to path of front document of application "Preview"\n'
         'do shell script "sips -s format jpeg " & quoted form of p & " --out " & quoted form of ((text 1 thru -5 of p) & ".jpg")"""'],
   wrong=['done "Exported Scan 12.jpg"'])

sc("sips-done", C, "save a jpeg copy of this pdf", p, last=['script shell """sips -s format jpeg … --out ~/Desktop/"Scan 12.jpg" """ -> ok'],
   script_output="/Users/arda/Desktop/Scan 12.pdf\n  /Users/arda/Desktop/Scan 12.jpg",
   accept=DONE, reject=[r"^script\b"], gold=['done "Saved Scan 12.jpg on your Desktop"'],
   wrong=['script shell """sips -s format jpeg ~/Desktop/"Scan 12.pdf" --out ~/Desktop/"Scan 12.jpg" """'])
