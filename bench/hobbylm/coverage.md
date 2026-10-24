# HobbyLM request coverage

`coverage.py` maps every frozen r4 task, all 15 System Settings navigation requests, and all Calculator held-out requests.
Mappings are explicit in `_mapping`; `args` says whether the catalog skill/flow can express the requested arguments.

| Source | ID | Kind | Request | Expected | Skill / flow | Args expressible? | Gap |
|---|---|---|---|---|---|---|---|
| hobbylm/sealed-r4 | C01 | calc | what's 82 plus 47 | 129 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C02 | calc | 605 minus 288 | 317 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C03 | calc | 14 x 9 | 126 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C04 | calc | 196 divided by 7 | 28 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C05 | calc | 2175 + 830 | 3005 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C06 | calc | 4.8 times 5 | 24 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C07 | calc | 701 - 234 kya hota hai | 467 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C08 | calc | take 18 off 75 | 57 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C09 | calc | how much less is 55 than 130 | 75 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C10 | calc | strip 90 from 400 | 310 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C11 | calc | how many 5s go into 85 | 17 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C12 | calc | what's 26 short of 100 | 74 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C13 | calc | by how much is 680 bigger than 595 | 85 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C14 | calc | pull 41 out of 120 | 79 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C15 | calc | break 480 into 12 equal shares, each share? | 40 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C16 | calc | forty two plus nineteen | 61 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C17 | calc | half a dozen times eight | 48 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C18 | calc | two hundred fifty minus sixty five | 185 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C19 | calc | thirteen times fourteen | 182 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C20 | calc | three sixty divided by fifteen | 24 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C21 | calc | eighty eight plus seventy two | 160 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C22 | calc | five hundred minus one seventy five | 325 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C23 | calc | bought 5 pens for 175, cost of one pen | 35 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C24 | calc | pizza 1680 shared by 7 friends, each pays | 240 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C25 | calc | handed 500 for groceries of 318, how much change | 182 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C26 | calc | 9 bags with 45 kg each, total weight | 405 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C27 | calc | parking 40 per hour, stayed 3 hours, total | 120 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C28 | calc | shirt 1299 plus 199 shipping, final amount | 1498 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C29 | calc | bus covers 210 km in 3 hrs, speed | 70 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | C30 | calc | jar has 64 cookies, ate 27, how many remain | 37 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/sealed-r4 | D01 | device | laptop glow is insane, pull brightness down | BRIGHTNESS_DOWN | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D02 | device | less bright please, night time | BRIGHTNESS_DOWN | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D03 | device | this display is blasting light at me | BRIGHTNESS_DOWN | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D04 | device | bump the brightness up | BRIGHTNESS_UP | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D05 | device | screen faded, more light needed | BRIGHTNESS_UP | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D06 | device | outdoor and screen gone blackish, brighten it | BRIGHTNESS_UP | set_brightness | no | Skill requires an absolute level; request gives direction only. |
| hobbylm/sealed-r4 | D07 | device | sound is harsh, turn it down a notch | VOLUME_DOWN | change_volume | yes |  |
| hobbylm/sealed-r4 | D08 | device | volume kam karo thoda | VOLUME_DOWN | change_volume | yes |  |
| hobbylm/sealed-r4 | D09 | device | too much noise from speakers, lower | VOLUME_DOWN | change_volume | yes |  |
| hobbylm/sealed-r4 | D10 | device | i barely hear the podcast, up the volume | VOLUME_UP | change_volume | yes |  |
| hobbylm/sealed-r4 | D11 | device | make it louder for this video | VOLUME_UP | change_volume | yes |  |
| hobbylm/sealed-r4 | D12 | device | audio is whisper quiet, raise volume | VOLUME_UP | change_volume | yes |  |
| hobbylm/sealed-r4 | D13 | device | mute now, client joining zoom | MUTE | mute | yes |  |
| hobbylm/sealed-r4 | D14 | device | cut all sound | MUTE | mute | yes |  |
| hobbylm/sealed-r4 | D15 | device | zero audio, baby is napping next room | MUTE | mute | yes |  |
| hobbylm/sealed-r4 | K01 | dark | flip to dark theme, late night work | DARK_MODE ON | dark_mode | yes |  |
| hobbylm/sealed-r4 | K02 | dark | turn dark mode on | DARK_MODE ON | dark_mode | yes |  |
| hobbylm/sealed-r4 | K03 | dark | black ui please, white hurts | DARK_MODE ON | dark_mode | yes |  |
| hobbylm/sealed-r4 | K04 | dark | turn dark mode off | DARK_MODE OFF | dark_mode | yes |  |
| hobbylm/sealed-r4 | K05 | dark | bring back the light theme | DARK_MODE OFF | dark_mode | yes |  |
| hobbylm/sealed-r4 | K06 | dark | daytime now, leave the dark look | DARK_MODE OFF | dark_mode | yes |  |
| hobbylm/sealed-r4 | A01 | app | gotta scribble a quick note | OPEN Notes | open_app | yes |  |
| hobbylm/sealed-r4 | A02 | app | notes app open karo | OPEN Notes | open_app | yes |  |
| hobbylm/sealed-r4 | A03 | app | when is my next meeting | OPEN Calendar | open_app | yes |  |
| hobbylm/sealed-r4 | A04 | app | open the calendar | OPEN Calendar | open_app | yes |  |
| hobbylm/sealed-r4 | A05 | app | browse files on this mac | OPEN Finder | open_app | yes |  |
| hobbylm/sealed-r4 | A06 | app | open finder please | OPEN Finder | open_app | yes |  |
| hobbylm/sealed-r4 | A07 | app | fire up music | OPEN Music | open_app | yes |  |
| hobbylm/sealed-r4 | A08 | app | i want the music app open | OPEN Music | open_app | yes |  |
| hobbylm/sealed-r4 | A09 | app | pull up my reminders | OPEN Reminders | open_app | yes |  |
| hobbylm/sealed-r4 | A10 | app | reminders kholo, need my todo | OPEN Reminders | open_app | yes |  |
| hobbylm/sealed-r4 | F01 | folder | where did chrome drop that zip | FOLDER Downloads | open_folder | yes |  |
| hobbylm/sealed-r4 | F02 | folder | open the downloads folder | FOLDER Downloads | open_folder | yes |  |
| hobbylm/sealed-r4 | F03 | folder | show whatever is sitting on desktop | FOLDER Desktop | open_folder | yes |  |
| hobbylm/sealed-r4 | F04 | folder | desktop folder open | FOLDER Desktop | open_folder | yes |  |
| hobbylm/sealed-r4 | F05 | folder | need papers from documents | FOLDER Documents | open_folder | yes |  |
| hobbylm/sealed-r4 | F06 | folder | open documents please | FOLDER Documents | open_folder | yes |  |
| hobbylm/sealed-r4 | T01 | timer | timer for 18 minutes | TIMER 18 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T02 | timer | remind me in an hour and a half | TIMER 90 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T03 | timer | set 45 min timer | TIMER 45 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T04 | timer | ping me in 2 hrs 20 min | TIMER 140 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T05 | timer | seven minute timer for eggs | TIMER 7 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T06 | timer | timer of half an hour | TIMER 30 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T07 | timer | remind me after 4 hours to stretch | TIMER 240 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | T08 | timer | ninety five mins timer | TIMER 95 | start_timer | yes | start_timer is declared in the catalog but not implemented in HandsKit. |
| hobbylm/sealed-r4 | S01 | screenshot | snap my screen | SCREENSHOT | take_screenshot | yes |  |
| hobbylm/sealed-r4 | S02 | screenshot | take screenshot now | SCREENSHOT | take_screenshot | yes |  |
| hobbylm/sealed-r4 | S03 | screenshot | screen capture please | SCREENSHOT | take_screenshot | yes |  |
| hobbylm/sealed-r4 | S04 | screenshot | ss of this window | SCREENSHOT | take_screenshot | yes |  |
| hobbylm/sealed-r4 | N01 | none | will it rain in mumbai tonight | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N02 | none | whatsapp meena that dinner is at 8 | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N03 | none | open reddit.com | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N04 | none | 20 times 3 then subtract 10 | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N05 | none | hey how was your weekend | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N06 | none | which is the brightest galaxy | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N07 | none | blast loud music on apple music | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N08 | none | figure out my income tax | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N09 | none | open a private window in firefox | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N10 | none | set alarm for 5:30 am | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N11 | none | find the screenshot from last week | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N12 | none | what does mute mean in music | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N13 | none | convert 100 euros to inr | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N14 | none | order groceries on blinkit | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N15 | none | why wont volume buttons work | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | N16 | none | suggest a podcast for focus | UNKNOWN | REFUSE | yes |  |
| hobbylm/sealed-r4 | E01 | event | coffee with Meera wednesday 10am | EVENT Coffee with Meera \| wednesday \| 10:00 \| Meera | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E02 | event | catch up w/ Dev sat 6pm | EVENT Catch up with Dev \| sat \| 18:00 \| Dev | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E03 | event | 1:1 with Sneha tomorrow 2:30pm IST | EVENT 1:1 with Sneha \| tomorrow \| 14:30 IST \| Sneha | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E04 | event | walkthrough with Omar monday 11 am GMT | EVENT Walkthrough with Omar \| monday \| 11:00 GMT \| Omar | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E05 | event | brainstorm w/ Kavya next tuesday 4pm | EVENT Brainstorm with Kavya \| next tuesday \| 16:00 \| Kavya | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E06 | event | call Rohan fri 9:15 am | EVENT Call with Rohan \| fri \| 09:15 \| Rohan | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E07 | event | office hours with Tanvi today 5pm | EVENT Office hours with Tanvi \| today \| 17:00 \| Tanvi | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E08 | event | yoga with Neha thursday 7am | EVENT Yoga with Neha \| thursday \| 07:00 \| Neha | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E09 | event | pitch practice with Vikram 12 nov 3pm EST | EVENT Pitch practice with Vikram \| 12 nov \| 15:00 EST \| Vikram | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E10 | event | dinner w/ Aditi sunday 8:30pm | EVENT Dinner with Aditi \| sunday \| 20:30 \| Aditi | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E11 | event | sync with maya.chen@example.com tmrw 9am PST | EVENT Sync with maya.chen@example.com \| tmrw \| 09:00 PST \| maya.chen@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E12 | event | interview james.lee@example.com wed 2pm | EVENT Interview with james.lee@example.com \| wed \| 14:00 \| james.lee@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E13 | event | demo for ravi.p@example.com 30 oct 6pm IST | EVENT Demo for ravi.p@example.com \| 30 oct \| 18:00 IST \| ravi.p@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E14 | event | onboarding call w/ sofia@example.com friday 10:00 CET | EVENT Onboarding call with sofia@example.com \| friday \| 10:00 CET \| sofia@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E15 | event | checkin with alex.ng@example.com today 4:45pm | EVENT Checkin with alex.ng@example.com \| today \| 16:45 \| alex.ng@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E16 | event | review session for nina@example.com monday 1pm UTC | EVENT Review session for nina@example.com \| monday \| 13:00 UTC \| nina@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E17 | event | add call w/ hari@example.com next friday 11:30 | EVENT Call with hari@example.com \| next friday \| 11:30 \| hari@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E18 | event | partner chat with ken.wong@example.com 8 nov 9am SGT | EVENT Partner chat with ken.wong@example.com \| 8 nov \| 09:00 SGT \| ken.wong@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E19 | event | follow up emailer@example.com thursday 3:15pm | EVENT Follow up with emailer@example.com \| thursday \| 15:15 \| emailer@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E20 | event | intro call for zoe.m@example.com sat 12pm | EVENT Intro call for zoe.m@example.com \| sat \| 12:00 \| zoe.m@example.com | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E21 | event | deep work block today 8am | EVENT Deep work block \| today \| 08:00 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E22 | event | haircut appointment tuesday 6pm | EVENT Haircut appointment \| tuesday \| 18:00 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E23 | event | flight checkin reminder 15 nov 5am | EVENT Flight checkin reminder \| 15 nov \| 05:00 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E24 | event | budget review tmrw 7:30pm | EVENT Budget review \| tmrw \| 19:30 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E25 | event | add focus time friday 2pm IST | EVENT Focus time \| friday \| 14:00 IST \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E26 | event | visa appointment 22 oct 10:30am | EVENT Visa appointment \| 22 oct \| 10:30 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E27 | event | morning run wednesday 6:15 | EVENT Morning run \| wednesday \| 06:15 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E28 | event | block sunday 4pm for laundry | EVENT Laundry \| sunday \| 16:00 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E29 | event | pharmacy pickup next monday 11am | EVENT Pharmacy pickup \| next monday \| 11:00 \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/sealed-r4 | E30 | event | tax paperwork 1 nov 9am GMT | EVENT Tax paperwork \| 1 nov \| 09:00 GMT \| none | create_event | no | Skill has no invitee/attendee argument. |
| hobbylm/system-settings | D1 | settings | Open System Settings and navigate to Sound. | Sound | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | D2 | settings | Open System Settings and navigate to Displays. | Displays | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | D3 | settings | Open System Settings and navigate to Keyboard. | Keyboard | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H01 | settings | Open System Settings and navigate to Wallpaper. | Wallpaper | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H02 | settings | Open System Settings and navigate to Wallpaper. | Wallpaper | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H03 | settings | Open System Settings and navigate to Bluetooth. | Bluetooth | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H04 | settings | Open System Settings and navigate to Notifications. | Notifications | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H05 | settings | Open System Settings and navigate to Appearance. | Appearance | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H06 | settings | Open System Settings and navigate to Battery. | Battery | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H07 | settings | Open System Settings and navigate to Trackpad. | Trackpad | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H08 | settings | Open System Settings and navigate to Control Centre. | Control Centre | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H09 | settings | Open System Settings and navigate to Lock Screen. | Lock Screen | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H10 | settings | Open System Settings and navigate to Printers & Scanners. | Printers & Scanners | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H11 | settings | Open System Settings and navigate to Wi‑Fi. | Wi‑Fi | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/system-settings | H12 | settings | Open System Settings and navigate to Game Center. | Game Center | MULTI_STEP | no | No native System Settings navigation skill. |
| hobbylm/calc-tasks/dev | D01 | calc | add 2 and 3 | 5 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks/dev | D02 | calc | subtract 1 from 9 | 8 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks/dev | D03 | calc | 4 bags of 6 sweets, how many sweets? | 24 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks/dev | D04 | calc | ten minus four | 6 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-01 | calc | add 7 and 5 | 12 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-02 | calc | 9 plus 6 | 15 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-03 | calc | what is 8 times 7 | 56 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-04 | calc | 20 minus 8 | 12 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-05 | calc | 81 divided by 9 | 9 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-06 | calc | multiply 12 by 3 | 36 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-07 | calc | sum of 14 and 29 | 43 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-08 | calc | 100 minus 37 | 63 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-09 | calc | 4.5 plus 2.5 | 7 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | simple-10 | calc | 45 divided by 5 | 9 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-11 | calc | subtract 3 from 10 | 7 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-12 | calc | take 15 away from 40 | 25 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-13 | calc | subtract 4 from 19 | 15 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-14 | calc | what is 6 less than 20 | 14 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-15 | calc | take 7 away from 50 | 43 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-16 | calc | subtract 12 from 30 | 18 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-17 | calc | how much bigger is 25 than 9 | 16 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | reversed-18 | calc | what is 9 less than 31 | 22 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-19 | calc | I had 20 rupees and spent 7. How much is left? | 13 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-20 | calc | three times four | 12 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-21 | calc | what's double 18 | 36 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-22 | calc | half of 18 | 9 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-23 | calc | split 60 equally among 4 people | 15 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-24 | calc | I bought 3 pens at 12 each, what is the total? | 36 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-25 | calc | a dozen plus 5 | 17 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-26 | calc | seven and five together | 12 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-27 | calc | my bill is 450 and I pay 500, how much change? | 50 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-28 | calc | two hundred minus fifty | 150 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-29 | calc | 5 boxes with 8 apples each, how many apples? | 40 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |
| hobbylm/calc-tasks | messy-30 | calc | 100 shared by 5 | 20 | MULTI_STEP | no | No calculator/arithmetic skill; needs app flow and computed value. |

## Ranked coverage gaps

| Rank | Gap | Requests blocked |
|---:|---|---:|
| 1 | No calculator/arithmetic skill; needs app flow and computed value. | 64 |
| 2 | Skill has no invitee/attendee argument. | 30 |
| 3 | No native System Settings navigation skill. | 15 |
| 4 | start_timer is declared in the catalog but not implemented in HandsKit. | 8 |
| 5 | Skill requires an absolute level; request gives direction only. | 6 |
