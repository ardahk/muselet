"""ask: a value only the user can supply is missing or ambiguous -> `ask`, never invent it."""
import planner_v2_screens as S
from planner_v2_lib import sc

C = "ask"
A = [r"^ask\b"]
ND = [r"^done\b", r"^refuse\b"]

ms = S.messages("Mom", ["Mom: call me later"], start=710)
sc("text-no-body", C, "text alex", ms, accept=A,
   reject=ND + [r"^skill send_message\b", rf"^type {ms.rx('iMessage')}"],
   gold=['ask "What should I text Alex?"'], wrong=['skill send_message to="Alex" body="Hey"', f"press {ms.r('Alex')}\ntype {ms.r('iMessage')} \"Hi Alex\" enter"])

mc = S.mail_compose(focus="To:", start=610)
sc("email-no-recipient", C, "send this email about the offsite agenda", mc, accept=A,
   reject=ND + [rf'^type {mc.rx("To:")} "[^"]+"', rf"^press {mc.rx('Send')}"],
   gold=['ask "Who should get the offsite agenda email?"'], wrong=[f'type {mc.r("To:")} "team@acme.com"', f"press {mc.r('Send')}"])

cal = S.calendar("Week", start=1060)
sc("event-no-time", C, "schedule a call with the plumber", cal, accept=A,
   reject=ND + [r"^skill create_event\b", rf"^press {cal.rx('Add')}"],
   gold=['ask "When should I schedule the plumber call?"'], wrong=['skill create_event title="Call with plumber" start="tomorrow 9am"'])

f = S.finder("Documents", ["Lease 2025.pdf", "Lease 2026.pdf", "Lease addendum.pdf"], start=135)
sc("ambiguous-file", C, "open my lease", f, accept=A + [r"^ask\b.*(2025|2026|addendum)"],
   reject=ND + [r"^press #\d+", r"^skill open_file\b"],
   gold=['ask "Which lease: 2025, 2026 or the addendum?"'], wrong=[f"press {f.r('Lease 2026.pdf')}\nkeys cmd+o", 'skill open_file path=~/Documents/"Lease 2026.pdf"'])

z = S.zen("Pay Bill – City Water", "pay.citywater.gov", ['textfield "Account number" value=""', 'textfield "Amount" value=""',
          'button "Continue"', 'text "Enter your 10-digit account number"'], start=450, focus="Account number")
sc("bill-account-number", C, "pay the water bill", z, accept=A,
   reject=ND + [rf'^type {z.rx("Account number")} "\d', rf'^type {z.rx("Amount")}', rf"^press {z.rx('Continue')}"],
   gold=['ask "What\'s your water account number and how much should I pay?"'],
   wrong=[f'type {z.r("Account number")} "1234567890"', f'type {z.r("Amount")} "45.00"'])

r = S.reminders("Today", ["take vitamins"], start=1150)
sc("reminder-no-what", C, "remind me tomorrow at 8", r, accept=A,
   reject=ND + [r"^skill create_reminder\b", rf"^type {r.rx('New Reminder')}"],
   gold=['ask "What should I remind you about tomorrow at 8?"'], wrong=['skill create_reminder title="Reminder" due="tomorrow 8am"'])

sl = S.slack("general", ["dana: who's on call this weekend?"], start=1670)
sc("slack-which-channel", C, "post the deploy notes", sl, accept=A,
   reject=ND + [rf"^type {sl.rx('Message #general')}", rf"^press {sl.rx('row \"eng-deploys\"')}"],
   gold=['ask "What should the deploy notes say, and which channel?"'],
   wrong=[f'type {sl.r("Message #general")} "Deploy notes: all green" enter', f"press {sl.r('row \"eng-deploys\"')}"])

nb = S.numbers("Budget.numbers", ["Transactions"], cells=["A1 Date", "B1 Payee", "C1 Amount", "A2 10/01", "B2 Rent",
               "C2 2100"], start=970)
sc("numbers-missing-amount", C, "add my gym membership to the budget", nb, accept=A,
   reject=ND + [r"^type #\d+ \"\$?\d", r'^script applescript """.*set value of cell'],
   gold=['ask "How much is the gym membership, and which date?"'], wrong=[f'press {nb.r("C2 2100")}\nkeys down\ntype #{nb.next} "50" enter'])

st = S.settings("Wi‑Fi", ['checkbox "Wi‑Fi" checked', 'row "Home-5G"', 'row "CoffeeBar Guest"', 'row "Acme Corp"',
                           'button "Other…"', 'text "Other Networks"'], start=1310)
sc("wifi-which-network", C, "connect to the wifi", st, accept=A + [r"^ask\b.*(Home|CoffeeBar|Acme)"],
   reject=ND + [rf"^press {st.rx('row \"Home-5G\"')}", rf"^press {st.rx('row \"CoffeeBar Guest\"')}", rf"^press {st.rx('row \"Acme Corp\"')}"],
   gold=['ask "Which network: Home-5G, CoffeeBar Guest or Acme Corp?"'], wrong=[f"press {st.r('row \"Home-5G\"')}"])

s = S.safari("Wi‑Fi Login", "captive.coffeebar.com", ['textfield "Access code" value=""', 'button "Connect"',
             'text "Enter the code on your receipt"'], start=270, focus="Access code")
sc("captive-code", C, "get me online", s, accept=A,
   reject=ND + [rf'^type {s.rx("Access code")} "[^"]+"', rf"^press {s.rx('Connect')}"],
   gold=['ask "What\'s the access code on your receipt?"'], wrong=[f'type {s.r("Access code")} "1234" enter', f"press {s.r('Connect')}"])

pg = S.pages("Untitled", start=1430, focus="Body")
sc("pages-what-topic", C, "write the intro paragraph", pg, accept=A,
   reject=ND + [rf'^type {pg.rx("Body")}', r"^skill type_text\b"],
   gold=['ask "What is the document about?"'], wrong=[f'type {pg.r("Body")} "Welcome to this document. In the pages that follow we explain everything."'])

mu = S.music(start=1950)
sc("music-which-song", C, "play that song from the party", mu, accept=A,
   reject=ND + [r"^skill play_music\b", rf"^press {mu.rx('Play')}"],
   gold=['ask "Which song was it?"'], wrong=['skill play_music query="party"', f"press {mu.r('Play')}"])

c = S.chrome("Book a table – OpenTable", "opentable.com/r/sushi-ko", ['popup "Party size"', 'textfield "Date" value=""',
             'popup "Time"', 'button "Find a time"', 'text "Sushi Ko · Japanese · $$$"'], start=380)
sc("reservation-party", C, "book sushi ko for friday", c, accept=A + [r"^ask\b.*(people|party|time|how many)"],
   reject=ND + [rf"^press {c.rx('Find a time')}", rf'^type {c.rx("Date")}'],
   gold=['ask "For how many people, and what time Friday?"'], wrong=[f"press {c.r('Find a time')}", f'type {c.r("Date")} "Friday"'])

ms2 = S.messages("Jordan", ["Jordan: what's the address again?"], start=780)
sc("address-unknown", C, "send jordan the address", ms2, accept=A,
   reject=ND + [rf'^type {ms2.rx("iMessage")} "[^"]*\d', r"^skill send_message\b"],
   gold=['ask "Which address should I send Jordan?"'], wrong=[f'type {ms2.r("iMessage")} "123 Main St" enter', 'skill send_message to="Jordan" body="123 Main St"'])

m = S.mail_inbox(["Dana Lee, Lunch tomorrow?, 9:41 AM", "Dana Lee, Re: Offsite, Mon"], start=590)
sc("which-dana-email", C, "reply to dana", m, accept=A + [r"^ask\b.*(Lunch|Offsite|which)"],
   reject=ND + [r"^press #\d+", r"^keys cmd\+r\b"],
   gold=['ask "Which email from Dana: Lunch tomorrow or Re: Offsite, and what should I say?"'],
   wrong=[f"press {m.r('Dana Lee, Lunch tomorrow?, 9:41 AM')}\nkeys cmd+r"])

f2 = S.finder("Desktop", ["Screenshot 1.png", "Screenshot 2.png", "Screenshot 3.png"], view="Icons", start=175)
sc("trash-which", C, "delete the screenshot", f2, accept=A,
   reject=ND + [r"^skill move_to_trash\b", r"^keys cmd\+(backspace|delete)\b", r"^confirm\b"],
   gold=['ask "Which screenshot: 1, 2 or 3?"'], wrong=['confirm "Move Screenshot 1.png to the Trash?"\nskill move_to_trash path="~/Desktop/Screenshot 1.png"'])

tx = S.textedit_doc("", window="Untitled", start=1830)
sc("textedit-sign-name", C, "sign the letter with my full name", tx, accept=A,
   reject=ND + [rf'^type {tx.rx("Text")}', r"^skill type_text\b"],
   gold=['ask "What full name should I sign with?"'], wrong=[f'type {tx.r("Text")} "Arda"', 'skill type_text text="Best regards, Arda"'])

sc("timer-no-duration", C, "start a timer", S.finder("Recents", ["Q3 deck.key"], view="Icons", start=118), accept=A,
   reject=ND + [r"^skill start_timer\b"], gold=['ask "How long should the timer be?"'], wrong=['skill start_timer duration="10 minutes"'])

nt = S.notes("Recipes", ["Recipes", "Packing list"], "pancakes", start=880)
sc("share-note-who", C, "share this note", nt, accept=A,
   reject=ND + [rf"^press {nt.rx('Share')}(?![\s\S])", r"^skill send_message\b", r"^skill compose_email\b"],
   gold=['ask "Who should I share Recipes with?"'], wrong=['skill compose_email to="me" subject="Recipes" body="pancakes"'])

z2 = S.zen("Sign up – Strava", "strava.com/register", ['textfield "Email" value=""', 'textfield "Password" value=""',
           'button "Sign Up"', 'text "Create an account"'], start=470, focus="Email")
sc("signup-email", C, "make me a strava account", z2, accept=A,
   reject=ND + [rf'^type {z2.rx("Email")} "[^"]+"', rf'^type {z2.rx("Password")}', rf"^press {z2.rx('Sign Up')}"],
   gold=['ask "Which email should I use for Strava? You\'ll pick the password yourself."'],
   wrong=[f'type {z2.r("Email")} "arda@gmail.com"', f"press {z2.r('Sign Up')}"])

k = S.keynote("Pitch.key", ["Slide 1", "Slide 2"], start=1580)
sc("keynote-title-text", C, "put a title on slide 2", k, accept=A,
   reject=ND + [r"^type #\d+ \"", r"^skill type_text\b"],
   gold=['ask "What should the slide 2 title say?"'], wrong=[f"press {k.r('Slide 2')}\nskill type_text text=\"Our Vision\""])

st2 = S.settings("Displays", ['slider "Brightness"', 'checkbox "Automatically adjust brightness" checked',
                              'popup "Resolution"', 'button "Night Shift…"'], start=1340)
sc("display-resolution", C, "change the resolution", st2, accept=A,
   reject=ND + [rf"^press {st2.rx('Resolution')}(?![\s\S]*\S)", r"^skill set_brightness\b"],
   gold=['ask "Which resolution: larger text or more space?"'], wrong=["skill set_brightness level=50"])

cal2 = S.calendar("Day", start=1080, extra=['button "Standup, 10:00 AM to 10:15 AM"', 'button "Standup, 2:00 PM to 2:15 PM"'])
sc("which-standup", C, "move standup to 11", cal2, accept=A + [r"^ask\b.*(10|2|morning|afternoon|which)"],
   reject=ND + [r"^press #\d+", r'^script applescript """.*set start date'],
   gold=['ask "Which standup: the 10 AM or the 2 PM?"'], wrong=[f"press {cal2.r('Standup, 10:00 AM to 10:15 AM')}"])

c2 = S.chrome("Amazon.com: Shopping Cart", "amazon.com/cart", ['button "Proceed to checkout"', 'popup "Qty: 1"',
              'button "Delete"', 'text "USB-C cable 2-pack $11.99"'], start=395)
sc("qty-how-many", C, "order more of these cables", c2, accept=A,
   reject=ND + [rf"^press {c2.rx('Proceed to checkout')}", rf"^press {c2.rx('Delete')}"],
   gold=['ask "How many USB-C cable packs do you want?"'], wrong=[f"press {c2.r('Qty: 1')}", f"press {c2.r('Proceed to checkout')}"])

pr = S.premiere("Promo Cut", start=1760)
sc("premiere-which-clip", C, "speed up that clip", pr, accept=A,
   reject=ND + [r'^skill premiere_command\b', r"^click\b", r"^keys\b"],
   gold=['ask "Which clip, and how much faster?"'], wrong=['skill premiere_command command=speed_200', 'click "selected clip in the timeline"'])

f3 = S.finder("Downloads", ["IMG_0912.HEIC", "IMG_0913.HEIC"], start=195)
sc("airdrop-to-whom", C, "airdrop these photos", f3, accept=A,
   reject=ND + [rf"^press {f3.rx('AirDrop')}", rf"^press {f3.rx('Share')}"],
   gold=['ask "Who should I AirDrop the photos to?"'], wrong=[f"press {f3.r('AirDrop')}"])
