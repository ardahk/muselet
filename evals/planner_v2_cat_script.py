"""script: work the AX tree can't do well (sheet math, bulk file ops, app scripting) goes through `script`; the reply
reads `Script result` back instead of guessing, and never re-runs a script that already answered."""
import planner_v2_screens as S
from planner_v2_lib import sc

C = "script"
ND = [r"^done\b"]
SH = r'^script shell """'
AS = r'^script applescript """'
F0 = S.finder("Recents", ["Q3 deck.key"], view="Icons", start=100)

f = S.finder("Downloads", [f"IMG_09{i}.HEIC" for i in range(10, 16)], start=230)
sc("count-heic", C, "how many heic photos are in downloads", f, accept=[SH + r".*\.(HEIC|heic)"], reject=ND,
   gold=['script shell """ls ~/Downloads/*.HEIC | wc -l"""'], wrong=['done "There are 6 HEIC photos"'])

sc("count-heic-result", C, "how many heic photos are in my downloads folder", f, last=['script shell """ls ~/Downloads/*.HEIC | wc -l""" -> ok'],
   script_output="      14", accept=[r"^done\b.*\b14\b"], reject=[r"^script\b", r"^done\b(?!.*\b14\b)"],
   gold=['done "14 HEIC photos in Downloads"'], wrong=['done "6 HEIC photos in Downloads"', 'script shell """ls ~/Downloads/*.HEIC | wc -l"""'])

sc("disk-free", C, "how much disk space do i have left", F0, accept=[SH + r".*\bdf\b"], reject=ND,
   gold=['script shell """df -h / | tail -1"""'], wrong=['done "You have plenty of space"'])

sc("disk-free-result", C, "how much free space is on my disk", F0, last=['script shell """df -h / | tail -1""" -> ok'],
   script_output="/dev/disk3s1s1  1.8Ti  1.1Ti  612Gi    65%    /", accept=[r"^done\b.*612\s?(Gi|GB|G)"],
   reject=[r"^script\b", r"^done\b(?!.*612)"], gold=['done "612 GB free"'], wrong=['done "1.1 TB free"'])

nb = S.numbers("Budget.numbers", ["Transactions", "Summary"], cells=["A1 Date", "B1 Payee", "C1 Amount"], start=1100)
sc("numbers-avg", C, "what's the average amount on the transactions sheet", nb,
   accept=[AS + r'.*(sheet "Transactions"|sheet 1).*column "?C'], reject=ND + [rf"^press #\d+"],
   gold=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" of front document\n'
         'set {t, n} to {0, 0}\nrepeat with c in (cells 2 thru -1 of column "C")\nif value of c is not missing value then set {t, n} to {t + (value of c), n + 1}\n'
         'end repeat\nreturn t / n\nend tell"""'], wrong=[f"press {nb.r('C1 Amount')}", 'done "The average is about $120"'])

sc("numbers-avg-result", C, "average the amount column on transactions", nb,
   last=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" …""" -> ok'],
   script_output="86.3125", accept=[r"^done\b.*86\.3[01]?"], reject=[r"^script\b", r"^done\b(?!.*86\.3)"],
   gold=['done "The average is $86.31"'], wrong=['done "The average is $86"'])

sc("rename-batch", C, "rename the heic photos in downloads to trip-1, trip-2 and so on", f, accept=[SH + r".*\bmv\b", r"^confirm\b"],
   reject=ND, gold=['script shell """cd ~/Downloads && i=1; for f in IMG_*.HEIC; do mv -n "$f" "trip-$i.HEIC"; i=$((i+1)); done"""'],
   wrong=[f"press {f.r('IMG_0910.HEIC')}\nkeys return", 'done "Renamed them"'])

sc("largest-file", C, "what's the biggest file in downloads", f, accept=[SH + r".*(du|ls -S|sort|find)"], reject=ND,
   gold=['script shell """ls -S ~/Downloads | head -1"""'], wrong=[f"press {f.r('Size')}\ndone \"setup.dmg\""])

cal = S.calendar("Week", start=1180)
sc("calendar-count", C, "how many meetings do i have next week", cal, accept=[AS + r".*Calendar.*(events|count)", r'^script jxa """.*Calendar'],
   reject=ND, gold=['script applescript """set d to (current date) + 7 * days\ntell application "Calendar"\nset n to 0\n'
                    'repeat with c in calendars\nset n to n + (count of (events of c whose start date > (current date) and start date < d))\n'
                    'end repeat\nend tell\nreturn n"""'], wrong=[f"press {cal.r('Next')}\ndone \"4 meetings\""])

sc("calendar-count-result", C, "count my meetings for next week", cal, last=['script applescript """set d to (current date) + 7 * days …""" -> ok'],
   script_output="9", accept=[r"^done\b.*\b9\b"], reject=[r"^script\b", r"^done\b(?!.*\b9\b)"], gold=['done "9 meetings next week"'],
   wrong=['done "4 meetings next week"'])

sc("script-error-retry", C, "how many unread emails do i have", S.mail_inbox(["Dana Lee, Lunch tomorrow?, 9:41 AM"], start=780),
   last=['script applescript """tell application "Mail" to count of unread messages of inbox""" -> failed: exit 1; stderr: Can’t get unread messages of inbox. (-1728)'],
   accept=[AS + r".*unread count"], reject=ND + [r"count of unread messages"],
   gold=['script applescript """tell application "Mail" to get unread count of inbox"""'],
   wrong=['script applescript """tell application "Mail" to count of unread messages of inbox"""', 'done "No unread emails"'])

sc("ip-address", C, "what's my local ip address", F0, accept=[SH + r".*(ipconfig getifaddr|ifconfig)"], reject=ND,
   gold=['script shell """ipconfig getifaddr en0"""'], wrong=['done "192.168.1.10"', 'url "https://whatismyip.com"'])

sc("ip-result", C, "tell me my ip on the local network", F0, last=['script shell """ipconfig getifaddr en0""" -> ok'],
   script_output="10.0.0.142", accept=[r"^done\b.*10\.0\.0\.142"], reject=[r"^script\b", r"^done\b(?!.*10\.0\.0\.142)"],
   gold=['done "10.0.0.142"'], wrong=['done "10.0.0.1"'])

sc("zip-folder", C, "zip the receipts folder on my desktop", S.finder("Desktop", ["receipts", "todo.txt"], start=250),
   accept=[SH + r".*(zip -r|ditto -c)"], reject=ND, gold=['script shell """cd ~/Desktop && ditto -c -k --keepParent receipts receipts.zip"""'],
   wrong=['done "Zipped receipts"', 'script shell """zip ~/Desktop/receipts"""'])

sc("empty-output", C, "find pdfs in downloads modified today", f, last=['script shell """find ~/Downloads -name "*.pdf" -mtime -1""" -> ok'],
   script_output="", accept=[r"^done\b.*([Nn]o |[Nn]one|0 )"], reject=[r"^done\b(?!.*([Nn]o |[Nn]one|0 ))", r"^script\b"],
   gold=['done "No PDFs in Downloads were modified today"'], wrong=['done "Found the PDFs"'])

sc("keynote-slide-count", C, "how many slides are in this deck", S.keynote("Pitch.key", ["Slide 1", "Slide 2", "Slide 3"], start=1700),
   accept=[AS + r".*Keynote.*count of slides", r"^done\b.*\b3\b"], reject=[r"^done\b(?!.*\b3\b)"],
   gold=['done "3 slides"', 'script applescript """tell application "Keynote" to count of slides of front document"""'], wrong=['done "2 slides"'])

sc("long-list-trunc", C, "list the apps in my applications folder", F0,
   last=['script shell """ls /Applications""" -> ok'], script_output="Calendar.app\nFinder.app\nKeynote.app\nMail.app\nNumbers.app\nPages.app\nSafari.app\nSlack.app",
   accept=[r"^done\b.*(8|Calendar.*Safari|Keynote)"], reject=[r"^script\b", r"^done\b(?!.*(8|Keynote))"],
   gold=['done "8 apps: Calendar, Finder, Keynote, Mail, Numbers, Pages, Safari, Slack"'], wrong=['done "Here are your apps"'])

nb2 = S.numbers("Budget.numbers", ["Transactions"], start=1120)
sc("numbers-filter", C, "how much did i spend at whole foods", nb2, accept=[AS + r".*[Ww]hole [Ff]oods"], reject=ND,
   gold=['script applescript """tell application "Numbers" to tell table 1 of sheet "Transactions" of front document\nset t to 0\n'
         'repeat with r in rows 2 thru -1\nif (value of cell 2 of r as text) contains "Whole Foods" then set t to t + (value of cell 3 of r)\n'
         'end repeat\nreturn t\nend tell"""'], wrong=['done "About $300 at Whole Foods"'])

sc("script-timeout", C, "how big is my photos library", F0,
   last=['script shell """du -sh ~/Pictures/Photos\\ Library.photoslibrary""" -> failed: timed out'],
   accept=[r"^done\b.*(time|long|couldn)", r"^ask\b", SH + r".*(mdls|stat|-d ?0|du -s)"], reject=[r'^script shell """du -sh ~/Pictures/Photos'],
   gold=['done "Measuring the library timed out; it is very large"', 'ask "Measuring took too long. Should I try again with a longer wait?"'],
   wrong=['script shell """du -sh ~/Pictures/Photos\\ Library.photoslibrary"""'])

sc("uptime", C, "how long has my mac been on", F0, accept=[SH + r".*uptime"], reject=ND,
   gold=['script shell """uptime"""'], wrong=['done "About 3 days"'])

sc("reminders-count", C, "how many reminders are left in errands", S.reminders("Errands", ["a", "b"], start=1220),
   accept=[AS + r".*Reminders.*Errands", r"^done\b.*\b2\b"], reject=[r"^done\b(?!.*\b2\b)"],
   gold=['done "2 left in Errands"', 'script applescript """tell application "Reminders" to count (reminders of list "Errands" whose completed is false)"""'],
   wrong=['done "5 left in Errands"'])

sc("jxa-safari-tabs", C, "how many safari tabs do i have open", S.safari("Apple", "apple.com", [], start=460),
   accept=[r'^script (applescript|jxa) """.*(tabs|Safari)'], reject=ND,
   gold=['script applescript """tell application "Safari" to count of tabs of every window"""'], wrong=['done "1 tab"'])

sc("script-no-rerun", C, "what's the battery cycle count", F0,
   last=['script shell """system_profiler SPPowerDataType | grep "Cycle Count\"""" -> ok'], script_output="      Cycle Count: 212",
   accept=[r"^done\b.*212"], reject=[r"^script\b", r"^done\b(?!.*212)"], gold=['done "212 cycles"'],
   wrong=['script shell """system_profiler SPPowerDataType | grep "Cycle Count\""""'])

sc("convert-heic", C, "convert the heic photos in downloads to jpg", f, accept=[SH + r".*sips.*jpe?g"], reject=ND,
   gold=['script shell """cd ~/Downloads && for f in *.HEIC; do sips -s format jpeg "$f" --out "${f%.HEIC}.jpg"; done"""'],
   wrong=['done "Converted them"', f"press {f.r('IMG_0910.HEIC')}\nkeys cmd+o"])

ns = S.notes("Recipes", ["Recipes", "Packing list", "Home"], "pancakes", start=1000)
sc("notes-search-script", C, "which of my notes mention the wifi password", ns,
   accept=[AS + r".*Notes.*(contains|whose)", rf'^type {ns.rx("Search")} "[Ww]i-?[Ff]i'], reject=ND,
   gold=['script applescript """tell application "Notes" to get name of every note whose body contains "wifi""""'], wrong=['done "The Home note"'])

sc("python-calc", C, "what's 18% tip on 86.40", F0, accept=[r"^done\b.*15\.55", SH + r".*86\.4"], reject=[r"^done\b(?!.*15\.55)"],
   gold=['done "$15.55 tip ($101.95 total)"', 'script shell """python3 -c "print(round(86.40*0.18,2))" """'], wrong=['done "$15.12 tip"'])
