# Phase 1 generation: 2% sample (`sample2`)

Route items kept: 1658; ARGS items: 1353. 30 random items per label below (`*` = from a G3 context pair).

## Token usage

| model | calls | input tok | output tok |
|---|---|---|---|
| `claude-haiku-5-5` | 29 | 21,390 | 94,756 |
| `gpt-5.4-nano` | 12 | 4,730 | 13,998 |

## Rejects

| label / reason | n |
|---|---|
| move_to_trash|length | 1 |
| ASK|ask_nearest_skill_invalid | 1 |
| ASK|length | 3 |
| g3|g3_invalid_pair | 10 |

## Kept per label

| label | n |
|---|---|
| set_volume | 41 |
| change_volume | 41 |
| mute | 40 |
| set_brightness | 44 |
| dark_mode | 42 |
| wifi | 40 |
| sleep_display | 41 |
| battery_status | 41 |
| open_app | 41 |
| quit_app | 41 |
| hide_app | 40 |
| window_layout | 40 |
| open_url | 44 |
| web_search | 45 |
| open_folder | 41 |
| find_file | 42 |
| open_file | 45 |
| new_folder | 41 |
| move_to_trash | 44 |
| take_screenshot | 41 |
| start_timer | 41 |
| create_event | 43 |
| create_reminder | 42 |
| todays_agenda | 46 |
| new_note | 42 |
| media_control | 44 |
| play_music | 40 |
| send_message | 42 |
| compose_email | 43 |
| type_text | 44 |
| copy_selection | 42 |
| premiere_command | 43 |
| MULTI_STEP | 118 |
| ASK | 75 |
| REFUSE | 39 |
| ANSWER | 79 |

## set_volume (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Turn it down to 60 | `level=60` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Could you make volume 58? | `level=58` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=no ¦ last_action=change_volume delta=10 |
| Volume max | `level=100` | app=Mail ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Quiet it down to 22 | `level=22` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=no ¦ last_action=none |
| Increase volume to 73 | `level=73` | app=Mail ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Lower it to thirty | `level=30` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Volume to 99 | `level=99` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Make it 95 | `level=95` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Set volume to 27 | `level=27` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Lower volume to 28 | `level=28` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Set volume to 33 | `level=33` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=no ¦ last_action=none |
| Bring it to 74 | `level=74` | app=Music ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=take_screenshot region=full |
| Turn down to twenty percent | `level=20` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=no ¦ last_action=none |
| Turn volume down to 16 | `level=16` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set system volume to 45 | `level=45` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Bring volume to 25 | `level=25` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=no ¦ last_action=none |
| Set volume to 100 now | `level=100` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Make it 10 percent quieter | `level=90` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=no ¦ last_action=none |
| Put volume at 31 | `level=31` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set volume to ninety | `level=90` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn volume down to zero | `level=0` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set volume to 24 | `level=24` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *turn it up | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Make it 66 percent | `level=66` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set volume to 12 percent | `level=12` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Make output volume 3 | `level=3` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Increase to 75 percent | `level=75` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set output volume to 35 | `level=35` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set it to 80 | `level=80` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=set_brightness level=50 |
| Can you raise volume to 60? | `level=60` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=no ¦ last_action=none |

## change_volume (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Would you bump the volume up just a touch? | `delta=10` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The volume feels too high—can you reduce it a bit? | `delta=-10` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Make it louder, please. | `delta=10` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| The sound is low, please turn it up. | `delta=10` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please lower the volume by one step. | `delta=-10` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I can barely hear it—can you raise the volume a little? | `delta=10` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you reduce the volume a little? | `delta=-10` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *turn it up | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you turn the audio up more for me? | `delta=10` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Make it quieter, please. | `delta=-10` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Please raise it slightly. | `delta=10` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you make it a bit quieter, please? | `delta=-10` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn it down quite a bit. | `delta=-25` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you turn the volume up a little? | `delta=10` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Can you make it louder, just a bit? | `delta=10` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| This is blasting—could you turn it down right now? | `delta=-10` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you make it quieter, just a bit? | `delta=-10` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Could you lower the volume slightly more, please? | `delta=-10` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| It’s too loud—could you lower the volume slightly? | `delta=-10` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| Please decrease the volume right away. | `delta=-10` | app=Music ¦ focused=button "Play" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Can you raise the volume slightly more, please? | `delta=10` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please turn the volume down a lot more. | `delta=-25` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you lower it substantially? | `delta=-25` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Sorry, could you turn it down a bit? | `delta=-10` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn it up quite a bit. | `delta=25` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Please make it louder than it is now. | `delta=10` | app=Finder ¦ focused=row "Downloads" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Please lower the volume slightly. | `delta=-10` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| The volume feels low—can you increase it a bit? | `delta=10` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please make it quieter than it is now. | `delta=-10` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you bump the volume up one notch? | `delta=10` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=change_volume delta=10 |

## mute (40 kept)

| request | args / nearest_skill | context |
|---|---|---|
| ugh, unmute, the video's playing with no sound | `on=false` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| so, uh, mute the sound on this thing, the mac | `on=true` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| um, can you go ahead and mute, or, mute the system audio | `on=true` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| silence it, um, the sound, the whole thing, please | `on=true` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=no ¦ last_action=none |
| okay, unmute the sound, um, I mean the mac | `on=false` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you, uh, take it off mute, the whole system | `on=false` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh, can you kill the sound? like completely mute it, thanks | `on=true` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh, could you turn the audio back on, unmute, thanks | `on=false` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| uh, unmute, wait, can you unmute the sound please | `on=false` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| let's, uh, let's unmute, the sound's still off | `on=false` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| sorry, what I meant was mute, mute the whole computer | `on=true` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| sorry, um, can you turn the mute off, like, unmute | `on=false` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| ugh, sorry, I need the sound off, um, mute it | `on=true` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| hey um, unmute the system, the whole thing, thanks | `on=false` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| well, I guess mute would be good, like, mute the audio | `on=true` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh, sound back on, please, unmute the computer | `on=false` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| hey, could you, uh, turn the sound back on, unmute it | `on=false` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need sound again, um, unmute, just unmute it | `on=false` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| so, like, I can't hear anything, unmute the thing | `on=false` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| okay mute, no, sorry, mute the system sound | `on=true` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| um so the audio is still off, like, unmute it | `on=false` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I think I need to mute, wait, is it muted? just mute it anyway | `on=true` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| okay so uh mute the sound, I'm about to, um, record | `on=true` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| unmute the speakers, I mean the system audio, yeah | `on=false` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| so, uh, is it muted? yeah, unmute it please | `on=false` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=none |
| okay so I'm on a call and, uh, mute my mac, actually mute the audio | `on=true` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| oh wait, unmute, the mac's still silent, unmute it | `on=false` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh, mute my laptop, the speakers are, you know, too loud | `on=true` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| um, would you mute the mac real quick, sorry, sorry | `on=true` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| so yeah unmute it, I think it's still muted, unmute | `on=false` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |

## set_brightness (44 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Is it possible to set brightness to 58? | `level=58` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you lower the screen brightness to 25 for me? | `level=25` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you make the display dimmer, like 40? | `level=40` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you make it a little brighter, like 65? | `level=65` | app=Google Chrome ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Is the screen able to go down to 0? | `level=0` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you turn the brightness up to 100? | `level=100` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind turning the brightness down to 20? | `level=20` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you go to max brightness? | `level=100` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Could you set the display to 22? | `level=22` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Is it possible to dim the display to 10? | `level=10` | app=Mail ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Can you put the brightness at half? | `level=50` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you crank the screen all the way up? | `level=100` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you set the display brightness to 5? | `level=5` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Can you make the screen brighter, maybe 88? | `level=88` | app=System Settings ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you bump the screen up to 80? | `level=80` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you set the brightness to 3, it's way too bright in here? | `level=3` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you set the screen to 2 percent, it's blinding me at night? | `level=2` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you lower the brightness to a quarter, so 25? | `level=25` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you set the brightness to 55 so I can see better? | `level=55` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind setting the brightness to 100? | `level=100` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you set brightness to 28, I'm trying to watch a movie? | `level=28` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Would you be able to set brightness to 99? | `level=99` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| *switch dark mode | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you go to 42 on the brightness? | `level=42` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you drop the display brightness to 8? | `level=8` | app=Safari ¦ focused=webarea "Google" ¦ selection=yes ¦ online=yes ¦ last_action=web_search query="weather" |
| Could you set brightness to 60 please? | `level=60` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| My eyes hurt, could you drop the brightness to 15? | `level=15` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you set the display to 90 percent? | `level=90` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you turn the screen brightness to 12? | `level=12` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *darker | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## dark_mode (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Something's off, my whole desktop is dark and I can't read the menus. | `on=false` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| The windows look muddy, I can't tell what's what. | `on=false` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| This white background is burning my retinas. | `on=true` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| It's the middle of the day and my screen looks like a cave. | `on=false` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The screen's way too bright for working at night. | `on=true` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *switch dark mode | `` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I'm trying to proofread this and the black background is hard to read. | `on=false` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Honestly the bright white everywhere is giving me a headache. | `on=true` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Working late and my screen feels like a flashlight. | `on=true` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| It's midnight and this screen is blinding me. | `on=true` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| This glare is unbearable, I can't see the text. | `on=true` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Everything's so bright right now, my head hurts. | `on=true` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *light mode | `` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Everything looks sad and gloomy, can you fix that? | `on=false` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I'm about to fall asleep and this white window is wrecking me. | `on=true` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| My eyes are fine, but this dim look is making everything hard to read. | `on=false` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| *darker | `` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Can this thing be less glaring? It's painful. | `on=true` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you make everything easier on my eyes tonight? | `on=true` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I want my screen looking crisp for the morning meeting. | `on=false` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The text in my documents looks washed out against the black. | `on=false` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| I'm trying to sleep and my laptop is lighting up the whole room. | `on=true` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can the screen brighten up a bit, everything's too grey. | `on=false` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| It's daytime, I don't need everything so dark. | `on=false` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| My designs look awful on this dark background, switch it back. | `on=false` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Ugh, I can't read anything with this glare. | `on=true` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| My eyes are killing me, this white screen is so bright. | `on=true` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Staring at this is brutal right now, my eyes are watering. | `on=true` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Sun's streaming in and I need things to look crisp again. | `on=false` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Could you bring back the bright look I had earlier? | `on=false` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |

## wifi (40 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Turn Wi‑Fi on | `on=true` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you turn wifi off real quick | `on=false` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Stop Wi‑Fi | `on=false` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Disable wireless, please | `on=false` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Wi-Fi off now | `on=false` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you turn wifi off | `on=false` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn the wifi off, thanks | `on=false` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Disable Wi-Fi | `on=false` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn Wi‑Fi off, please | `on=false` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need Wi‑Fi disabled | `on=false` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you turn off Wi‑Fi | `on=false` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn Wi‑Fi off right now | `on=false` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you switch Wi‑Fi off? | `on=false` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I want Wi‑Fi back on | `on=true` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I’m back—turn Wi‑Fi on | `on=true` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=no ¦ last_action=none |
| Do you mind turning wifi on? | `on=true` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Switch Wi‑Fi on for me | `on=true` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Switch off my Wi‑Fi please | `on=false` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn off wifi | `on=false` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Enable wireless networking | `on=true` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Wi-Fi on | `on=true` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn wireless on | `on=true` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please enable wifi | `on=true` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn on the WiFi connection | `on=true` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Turn wifi on please | `on=true` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Please turn wifi off | `on=false` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Enable Wi‑Fi please | `on=true` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Go ahead and turn off my wifi | `on=false` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Enable my Wi‑Fi now | `on=true` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please switch on Wi‑Fi | `on=true` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=no ¦ last_action=take_screenshot region=full |

## sleep_display (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Can you sleep it? | `` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Display off now | `` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Turn off the monitor | `` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screen off, could you? | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Sleep the display | `` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Blank the screen | `` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=no ¦ last_action=none |
| Turn off display | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Lights out, screen | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn my screen off | `` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Switch off the display | `` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn the monitor off | `` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Make the screen sleep | `` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=no ¦ last_action=none |
| Kill the display | `` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=no ¦ last_action=none |
| Screen off right now | `` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Darken the display | `` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screen off | `` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Sleep display now | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screen off, thanks | `` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Turn display off, please | `` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screen off, please | `` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay, screen off | `` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn screen off, thanks | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screen off now | `` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| Power down the screen | `` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Monitor off please | `` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Screen off, sleep mode | `` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn off monitor | `` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Sleep my screen | `` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Black out the screen | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Monitor to sleep | `` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |

## battery_status (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| How much battery do I have right now? | `` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| What’s the current state of charge? | `` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Is my Mac charging at the moment? | `` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Is it charging, or is it draining? | `` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please tell me my battery level right now. | `` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Are we on the charger? | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Battery status, please—charging or not? | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| What percent charge do I have remaining? | `` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I just need my battery percentage. | `` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Do I need to plug in? | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Is the battery charging or discharging? | `` | app=Music ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you report whether I’m charging? | `` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *what's my battery? | `` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you report my battery percent? | `` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| How full is the battery right now? | `` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you tell me my battery level? | `` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| How much power is left on my laptop? | `` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you check my battery status for me? | `` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| What's my battery percentage? | `` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Tell me my battery percentage and charging state. | `` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| What’s the charging status of my battery? | `` | app=Messages ¦ focused=row "Mom" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Is my Mac plugged in and charging? | `` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=media_control action=pause |
| Battery percent, please. | `` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Are you able to check battery status for me? | `` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Are we charging? | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Am I currently charging or not? | `` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| What’s my battery percentage at the moment? | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you check if I’m charging? | `` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you tell whether I’m charging? | `` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Do I have enough battery left? | `` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |

## open_app (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| open up messages | `app=messages` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open chrome | `app=chrome` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open firefox | `app=firefox` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| launch quicktime | `app=quicktime` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open numbers | `app=numbers` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=web_search query="weather" |
| launch terminal | `app=terminal` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open safari | `app=safari` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open preview | `app=preview` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open maps | `app=maps` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open notes | `app=notes` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| switch to slack | `app=slack` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open podcasts | `app=podcasts` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| launch vs code | `app="vs code"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| switch to word | `app=word` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| switch to notion | `app=notion` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| switch to messages | `app=messages` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open the app store | `app="app store"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| bring up zoom | `app=zoom` | app=Music ¦ focused=button "Play" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| launch discord | `app=discord` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| launch premiere | `app=premiere` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| open google chrome | `app="google chrome"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open system settings | `app="system settings"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open keynote | `app=keynote` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| fire up xcode | `app=xcode` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| launch premiere pro | `app="premiere pro"` | app=Mail ¦ focused=textarea "Message body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| launch pages | `app=pages` | app=Mail ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| open reminders | `app=reminders` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open spotify | `app=spotify` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| pull up photos | `app=photos` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| switch to finder | `app=finder` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |

## quit_app (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Could you please shut down App Store? | `app="App Store"` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you please quit Finder? It's acting up again. | `app=Finder` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Could you close Podcasts for me, please? | `app=Podcasts` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind quitting Chrome for me, thanks. | `app="Google Chrome"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you please quit Spotify for me? | `app=Spotify` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Please quit Google Chrome when you get a sec. | `app="Google Chrome"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you please close Notes, I'm finished writing. | `app=Notes` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please quit Microsoft Word now? | `app="Microsoft Word"` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you shut Microsoft Excel down for me? | `app="Microsoft Excel"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you mind closing Activity Monitor for me? | `app="Activity Monitor"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind closing Safari, please? | `app=Safari` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you quit FaceTime for me, please? | `app=FaceTime` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please close Reminders now? | `app=Reminders` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you please close Spotify, I'm heading out now. | `app=Spotify` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you go ahead and close Zoom for me? | `app=Zoom` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you close Calendar, I'm done with it. | `app=Calendar` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind closing Pages for me, please? | `app=Pages` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please quit Zoom now that the meeting's over? | `app=Zoom` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please shut down Terminal for me, would you? | `app=Terminal` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you please close Mail for me? | `app=Mail` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you please quit Slack completely for me? | `app=Slack` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Please quit Slack, I need to focus now. | `app=Slack` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you please close Visual Studio Code for me, thank you. | `app="Visual Studio Code"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Can you quit System Settings, please? | `app="System Settings"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Would you mind quitting Notion for me? | `app=Notion` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you quit Maps for me when you have a moment? | `app=Maps` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you please quit Numbers before we continue? | `app=Numbers` | app=Notes ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you mind shutting down Terminal for me? | `app=Terminal` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you kindly quit Firefox for me? | `app=Firefox` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you please quit Photos? Thanks a lot. | `app=Photos` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## hide_app (40 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Um, hide Finder, no, sorry, I mean, can you hide Finder | `app=Finder` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Ugh, hide Discord, sorry, it's just distracting, hide Discord please | `app=Discord` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Yo, hide Activity Monitor, no wait, hide Activity Monitor, it's staring at me | `app="Activity Monitor"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hmm, I think, uh, hide Premiere Pro? Yeah, that one, hide it | `app="Premiere Pro"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay so, um, the Zoom window is, uh, huge, can you hide Zoom | `app=Zoom` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Ah, hide Pages, no, sorry, Keynote, no, Pages, hide Pages | `app=Pages` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| So, uh, hide Microsoft Word, I mean, the Word doc, hide it | `app="Microsoft Word"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need, like, I need Photos hidden right now, um, hide Photos | `app=Photos` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Hmm, hide Google Chrome, um, I mean the browser, Chrome, yeah, hide it | `app="Google Chrome"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Yeah, uh, hide Calendar, I don't wanna see it right now, hide Calendar | `app=Calendar` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Yeah, um, hide QuickTime Player, it's, uh, playing something, hide it | `app="QuickTime Player"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Could you, like, uh, hide Safari, I mean, just Safari, hide it | `app=Safari` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Um, hide Notion, I think, yeah, Notion, can you hide that one | `app=Notion` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Sorry, I was gonna, uh, hide Google Chrome, can you do that | `app="Google Chrome"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Uh, hide Slack, wait, no, actually just hide Slack for now | `app=Slack` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay, hide, um, Finder, wait, that's not it, hide Safari, Safari | `app=Safari` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay so, hmm, hide VS Code, sorry, Visual Studio Code, hide that | `app="Visual Studio Code"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=none |
| Hey, could you, like, hide Messages? Oh wait, yeah, hide Messages | `app=Messages` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Uh, hide Maps, the, um, Maps window, I'm done with directions | `app=Maps` | app=Google Chrome ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Um, yeah, hide Zoom, I'm, uh, not on the call anymore so hide it | `app=Zoom` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you, um, hide Preview, it's, I dunno, in the way, hide it | `app=Preview` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you, uh, hide Mail, the email one, hide Mail | `app=Mail` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Hey, could you hide FaceTime? Sorry, um, my, uh, I'm not on it | `app=FaceTime` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay, hide App Store, sorry, I didn't mean to open that, hide App Store | `app="App Store"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Okay, uh, hide Music, the Music app, hide it for me | `app=Music` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Um, could you, uh, hide Xcode, I'm, like, done with it for today | `app=Xcode` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| So, uh, hide Firefox, can you, it's, like, the browser, hide Firefox | `app=Firefox` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hide Reminders, um, no, hide Reminders, yeah, it's cluttering stuff | `app=Reminders` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you hide Microsoft Excel, um, the spreadsheet thing, hide Excel | `app="Microsoft Excel"` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Uh, hide Terminal, sorry, my, uh, my bad, hide Terminal please | `app=Terminal` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |

## window_layout (40 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Can you snap it left half? | `layout=left` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you center this window instead? | `layout=center` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you resize this to the left side? | `layout=left` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| Would you center it for me? | `layout=center` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you move the current window to the right half? | `layout=right` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you place this window in the center? | `layout=center` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you resize it to full for me? | `layout=full` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you center the current window? | `layout=center` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| Could you resize this front window to the left half please? | `layout=left` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you snap it to the left half? | `layout=left` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you make this window fill the screen? | `layout=full` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=dark_mode on=true |
| Can you snap this window to the left side? | `layout=left` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=dark_mode on=true |
| Could you put this one on the right? | `layout=right` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you put this window on the left half of the display? | `layout=left` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you put this window on the right half now? | `layout=right` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you make the current window occupy the full space? | `layout=full` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you put this window on the left half? | `layout=left` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| How about making this window full screen? | `layout=full` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Can you set this to the right half please? | `layout=right` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| Would you resize this window to the left half? | `layout=left` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you snap this window to the right half? | `layout=right` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you move this window to the center of the screen? | `layout=center` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you move it to the center? | `layout=center` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you snap this window to the right half now? | `layout=right` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you expand this window to full size? | `layout=full` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you snap the front window to the right half? | `layout=right` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you put this window in the left half of the screen? | `layout=left` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you put this one on the right side half? | `layout=right` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Can you set this window to the right half? | `layout=right` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you maximize the frontmost window? | `layout=full` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## open_url (44 kept)

| request | args / nearest_skill | context |
|---|---|---|
| I might need https://calendar.google.com opened. | `url=https://calendar.google.com` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you open https://slack.com/workspace-signup? | `url=https://slack.com/workspace-signup?` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need https://www.chess.com opened, thanks. | `url=https://www.chess.com` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I just want https://www.notion.so opened, please. | `url=https://www.notion.so` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need https://www.weather.com opened, thanks. | `url=https://www.weather.com` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you open https://www.producthunt.com for me? | `url=https://www.producthunt.com` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Could you open https://www.pypi.org so I can check? | `url=https://www.pypi.org` | app=Messages ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| I’m trying to reach https://mail.google.com—can you open it? | `url=https://mail.google.com` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open downloads | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open https://www.reddit.com if you can. | `url=https://www.reddit.com` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Could you open https://www.crunchbase.com too? | `url=https://www.crunchbase.com` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I’m looking for https://www.microsoft.com—open it? | `url=https://www.microsoft.com` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you open https://www.wikipedia.org, please? | `url=https://www.wikipedia.org` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open this file | `` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| I’d like to see https://www.nytimes.com in a tab. | `url=https://www.nytimes.com` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Can you open https://www.adobe.com for reference? | `url=https://www.adobe.com` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would it be possible to open https://www.ted.com? | `url=https://www.ted.com` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you open https://www.docker.com homepage? | `url=https://www.docker.com` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| I need this: https://news.ycombinator.com | `url=https://news.ycombinator.com` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you open https://www.gutenberg.org for me? | `url=https://www.gutenberg.org` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you open https://docs.microsoft.com for me? | `url=https://docs.microsoft.com` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| *open url https://example.com | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you show https://maps.google.com in the browser? | `url=https://maps.google.com` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need to check https://www.stackoverflow.com real quick. | `url=https://www.stackoverflow.com` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need to read https://www.medium.com—open it? | `url=https://www.medium.com` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you open https://www.cnn.com for a minute? | `url=https://www.cnn.com` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Can you open https://www.zoom.us/join to start? | `url=https://www.zoom.us/join` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=none |
| Can you open https://www.github.io in a browser window? | `url=https://www.github.io` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Open https://developer.apple.com if possible. | `url=https://developer.apple.com` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| I’m trying to get to https://www.bbc.com, can you? | `url=https://www.bbc.com` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |

## web_search (45 kept)

| request | args / nearest_skill | context |
|---|---|---|
| yo search how to unclog a toilet without a plunger | `query="how to unclog a toilet without a plunger"` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=take_screenshot region=full |
| wanna see the weather in nola this weekend | `query="weather in nola this weekend"` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| yo can you google is creatine safe | `query="is creatine safe"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| *type hello | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| search fr the roadmap for learning rust | `query="roadmap for learning rust"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| look up nbd, how to say thank u in korean | `query="how to say thank you in korean"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can u look up if the cybertruck is worth it | `query="if the cybertruck is worth it"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| lmk what the tax deadline is, search it | `query="tax deadline this year"` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open url https://example.com | `` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| hit up google for cheap flights to vegas | `query="cheap flights to vegas"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you search for lo-fi study playlists | `query="lo-fi study playlists"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| search for that song that goes ooh ooh ooh baby | `query="song that goes ooh ooh ooh baby"` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| search for air fryer vs oven fries | `query="air fryer vs oven fries"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| ngl I need to google how long to boil an egg | `query="how long to boil an egg"` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| quick google, how many oz in a cup | `query="how many oz in a cup"` | app=Mail ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| can u look up how many calories in a banana | `query="how many calories in a banana"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| yo search what time does costco close | `query="what time does costco close"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can u search best budget mechanical keyboard under 100 | `query="best budget mechanical keyboard under 100"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *search the web for cats | `` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| lemme search how tall is mount fuji rn | `query="how tall is mount fuji"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| search tbh is it worth getting a peloton | `query="is it worth getting a peloton"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| yo google best tacos near me | `query="best tacos near me"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| pull up reddit threads about the new iphone battery | `query="reddit threads about the new iphone battery"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| pull up google results for ps5 vs xbox series x | `query="ps5 vs xbox series x"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| search for gluten free bagels nyc | `query="gluten free bagels nyc"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| yo can u google who played the bartender in cheers | `query="who played the bartender in cheers"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| google bday gift ideas for my gf | `query="bday gift ideas for my gf"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=start_timer duration="10 minutes" |
| gonna need u to google dog ate chocolate what to do | `query="dog ate chocolate what to do"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| search up that bougie coffee place near the gym | `query="bougie coffee place near the gym"` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| search for apartments with in-unit laundry in chicago | `query="apartments with in-unit laundry in chicago"` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |

## open_folder (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| open the desktop folder | `path=desktop` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open music folder | `path=music` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| bring up pictures | `path=pictures` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| pull up documents | `path=documents` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| show work folder | `path=work` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| open home folder | `path=home` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open downloads | `` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open iCloud Drive | `path="iCloud Drive"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| open my school folder | `path=school` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| go to desktop | `path=desktop` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open documents | `path=documents` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need my downloads | `path=downloads` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| open Backups folder | `path=Backups` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=take_screenshot region=full |
| show recent files | `path=Recents` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| open budget folder | `path=budget` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open downloads | `path=downloads` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open the shared folder | `path=shared` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open ~/Downloads/invoices | `path=~/Downloads/invoices` | app=Notes ¦ focused=textarea "Note body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| open Google Drive | `path="Google Drive"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Downloads please | `path=Downloads` | app=System Settings ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Pictures folder, please | `path="Pictures folder"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you open downloads | `path=downloads` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| navigate to Documents | `path=Documents` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| open my projects | `path=projects` | app=Slack ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=open_app app=Safari |
| open the Utilities folder | `path=Utilities` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| show my desktop | `path=desktop` | app=Finder ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=media_control action=pause |
| open /Users/sam/Desktop | `path=/Users/sam/Desktop` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| show Dropbox folder | `path=Dropbox` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| show the applications | `path=applications` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| open my resume folder | `path=resume` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |

## find_file (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Show results for the meeting notes | `query="meeting notes" kind=document` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you find the folder named invoices | `query=invoices kind=folder` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Find the document named budget spreadsheet | `query="budget spreadsheet" kind=document` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Locate the folder for website assets | `query="website assets" kind=folder` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the document with the phrase meeting agenda | `query="meeting agenda" kind=document` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the video containing the word demo | `query=demo kind=video` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Search for the presentation keynote file | `query=presentation kind=document` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *search the web for cats | `` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the document containing the phrase performance review | `query="performance review" kind=document` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you show me the folder for presentations | `query=presentations kind=folder` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you find the file called architecture diagram | `query="architecture diagram" kind=document` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Show documents containing the word invoice | `query=invoice kind=document` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Find PDFs with the phrase quarterly report | `query="quarterly report" kind=pdf` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Show me the image of the logo | `query=logo kind=image` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Search for the document about travel plans | `query="travel plans" kind=document` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Where's the PDF of my resume? | `query=resume kind=pdf` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Search for the document containing "project alpha" | `query="project alpha" kind=document` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Where are my receipts from last year | `query="receipts last year" kind=document` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Search for the photo of the bridge | `query=bridge kind=image` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Where's the document called product roadmap | `query="product roadmap" kind=document` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Search for the folder called taxes | `query=taxes kind=folder` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the PDF that mentions contract renewal | `query="contract renewal" kind=pdf` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the folder with the client proposals | `query="client proposals" kind=folder` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the screenshot of the error | `query=error kind=image` | app=Notes ¦ focused=textfield "Search" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Find my passport scan | `query="passport scan" kind=image` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Find files named system settings export | `query="system settings export" kind=document` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Find the video clip called intro | `query=intro kind=video` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Where did I put the PDF called onboarding | `query=onboarding kind=pdf` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Where did I save the contract pdf? | `query=contract kind=pdf` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=yes ¦ online=no ¦ last_action=mute on=true |
| Find videos from vacation | `query=vacation kind=video` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |

## open_file (45 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Open meeting_recording.mp4 | `path=meeting_recording.mp4` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Open that spreadsheet on my desktop | `path="that spreadsheet on my desktop"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open the README in my project folder | `path="the README in my project folder"` | app=Google Chrome ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Open the scan from the printer | `path="the scan from the printer"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open the first result | `` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Open the budget spreadsheet | `path="the budget spreadsheet"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open main.swift | `path=main.swift` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open grocery list | `path="grocery list"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Open the logo design dot ai | `path="logo design.ai"` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Launch invoice_march.pdf | `path=invoice_march.pdf` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open Downloads slash photo.heic | `path=Downloads/photo.heic` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *open this file | `` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Pull up budget.xlsx | `path=budget.xlsx` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| Open ~/Downloads/receipt_0412.png | `path=~/Downloads/receipt_0412.png` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open my tax return 2023 | `path="tax return 2023"` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open ~/Work/roadmap_2025.numbers | `path=~/Work/roadmap_2025.numbers` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Open the latest screenshot | `path="the latest screenshot"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open the Keynote deck for Monday | `path="the Keynote deck for Monday"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open resume.pdf | `path=resume.pdf` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open ~/Desktop/todo.txt | `path=~/Desktop/todo.txt` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=web_search query="weather" |
| Launch presentation.key | `path=presentation.key` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open the meeting notes file | `path="the meeting notes file"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open the Excel file from Dave | `path="the Excel file from Dave"` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open podcast_episode_12.m4a | `path=podcast_episode_12.m4a` | app=Messages ¦ focused=row "Mom" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Open the screenshot from this morning | `path="the screenshot from this morning"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open setup_notes.md | `path=setup_notes.md` | app=Notes ¦ focused=textarea "Note body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Open cover letter final dot pages | `path="cover letter final.pages"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open the latest screen recording | `path="the latest screen recording"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open ~/Documents/contract_v2.docx | `path=~/Documents/contract_v2.docx` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Open the last file I downloaded | `path="the last file I downloaded"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## new_folder (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Would you mind making a new folder called Clients inside the Work folder on my desktop? | `parent="the Work folder on my desktop" name=Clients` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you make a folder for me called Syllabus inside my School folder? | `parent="my School folder" name=Syllabus` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you create a folder called Holiday Cards on my desktop, please? | `parent="my desktop" name="Holiday Cards"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please create a folder named Client Projects on the desktop. | `parent="the desktop" name="Client Projects"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hi, could you make a folder called Contracts in Documents for me? | `parent=Documents name=Contracts` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you please make a folder named Music Samples in the Music folder? | `parent="the Music folder" name="Music Samples"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Would you make a new folder called Work Stuff on the Desktop, please? | `parent="the Desktop" name="Work Stuff"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you put a new folder called Screen Recordings in Movies, please? | `parent=Movies name="Screen Recordings"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you make a folder named Unsorted in Downloads, please? | `parent=Downloads name=Unsorted` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you make a folder on my desktop called Quick Share? | `parent="my desktop" name="Quick Share"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you make a folder called Logos in my Projects folder in Documents? | `parent="my Projects folder in Documents" name=Logos` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you make a folder named Meeting Notes in the Documents folder? | `parent="the Documents folder" name="Meeting Notes"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you make a new folder in the Movies folder called Rough Cuts? | `parent="the Movies folder" name="Rough Cuts"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| *make a new folder | `` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please create a folder named 2024 Photos in Pictures? | `parent=Pictures name="2024 Photos"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you please make a new folder called receipts on my desktop? | `parent="my desktop" name=receipts` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Would you be able to make a new folder named Podcast Episodes in Music? | `parent=Music name="Podcast Episodes"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Could you make a folder named Cover Art in my Music folder, please? | `parent="my Music folder" name="Cover Art"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you set up a new folder called Lab Results in Documents, please? | `parent=Documents name="Lab Results"` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hey, could you make a folder called recipes in my home folder? | `parent="my home folder" name=recipes` | app=Messages ¦ focused=row "Mom" ¦ selection=yes ¦ online=yes ¦ last_action=dark_mode on=true |
| Please make a folder called thesis drafts in Documents, thank you. | `parent=Documents name="thesis drafts"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you make a new folder called Fonts in my Library folder? | `parent="my Library folder" name=Fonts` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please go ahead and create a folder called Invoices under Documents. | `parent=Documents name=Invoices` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Would you kindly make a folder named Budget 2025 in Documents? | `parent=Documents name="Budget 2025"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you set up a folder called Wedding Photos in my Pictures folder, please? | `parent="my Pictures folder" name="Wedding Photos"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you make me a folder on the desktop called Scans, please? | `parent="the desktop" name=Scans` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I'd like a folder called Raw Footage made in Movies, if that's alright. | `parent=Movies name="Raw Footage"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please create a folder called Shared with Family in my home directory. | `parent="my home directory" name="Shared with Family"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind putting together a folder called Old Phones inside Archive? | `parent=Archive name="Old Phones"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you be able to add a folder called Screenshots to my Pictures? | `parent="my Pictures" name=Screenshots` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |

## move_to_trash (44 kept)

| request | args / nearest_skill | context |
|---|---|---|
| So the, uh, the Excel file, sales_2021_copy.xlsx, it's on my desktop, could you put it in the trash | `path=~/Desktop/sales_2021_copy.xlsx` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *trash this | `` | app=Finder ¦ focused=row "Downloads" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| So the, um, the old draft, the one in Pages, not the, uh, the newer one, can you trash it? | `path=~/Documents/old_draft.pages` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Like, can you delete, um, the whole Projects/old-site folder? Wait, is it in home or documents? Home. | `path=~/Projects/old-site` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hmm, let me think, I think the, uh, the resume_v3.docx thing in Documents is outdated, toss it? | `path=~/Documents/resume_v3.docx` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| So, um, I think I want to get rid of that, uh, presentation, the Keynote one, Pitch_Deck_old.key | `path=~/Documents/Pitch_Deck_old.key` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Um, so yeah, the, uh, the old Xcode project, MyApp_backup, can you move that to the trash? Thanks | `path=~/Developer/MyApp_backup` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Uh, could you trash everything in... no, just trash the single folder, Thesis Drafts, in Documents | `path="~/Documents/Thesis Drafts"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Uh, yeah, so trash the screenshots folder on my desktop, the one named Screenshots_March, not the other one | `path=~/Desktop/Screenshots_March` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hey, uh, could you, like, trash the invoice_march.pdf in Documents? I don't need it anymore, I think | `path=~/Documents/invoice_march.pdf` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Uh, trash the, the duplicate photo, IMG_1234 copy.jpg, on the desktop, I don't know why I made it | `path="~/Desktop/IMG_1234 copy.jpg"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Wait, hold on, uh, trash the Chrome extension folder I unpacked on the desktop, my_extension_test | `path=~/Desktop/my_extension_test` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Uh, yeah, so trash the, the test video, the one in Movies, IMG_0042.mov, I guess, yeah | `path=~/Movies/IMG_0042.mov` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Uh, could you delete the, the test file test_output.csv on my desktop, the one I made this morning | `path=~/Desktop/test_output.csv` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hmm, so yeah, the, uh, the old Keynote export, slides_old.pdf, trash that please, it's on the desktop | `path=~/Desktop/slides_old.pdf` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you, like, get rid of the, the voice memo, uh, Voice Memo 14, it's in Documents | `path="~/Documents/Voice Memo 14"` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=set_volume level=30 |
| Hey, uh, trash the notes file, the one on the desktop, meeting_notes_copy.rtf, I don't need two of them | `path=~/Desktop/meeting_notes_copy.rtf` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Yo, so, um, trash the, the Zoom recording folder from last week, it's in Documents, Zoom folder I think | `path=~/Documents/Zoom` | app=Calendar ¦ focused=button "Today" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Okay so, um, I don't need the, uh, the Spotify export, playlists_backup.json, can you just toss it | `path=~/Downloads/playlists_backup.json` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Hey, uh, can you get rid of the, the Notes export, uh, notes_export_old folder on the desktop | `path=~/Desktop/notes_export_old` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Um, the, the whole Podcasts download folder? Like, the one with the old episodes, trash that, can you | `path=~/Downloads/Podcasts` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Ugh, I, I mean, can you get rid of the screenshot on my desktop, the one called Screen Shot 2024 | `path="~/Desktop/Screen Shot 2024"` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Okay so, um, I need the, uh, the spreadsheet budget_final_FINAL.xlsx gone, can you trash that for me | `path=~/Documents/budget_final_FINAL.xlsx` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Could you um, trash the random zip called archive.zip in Downloads, I downloaded it like, months ago | `path=~/Downloads/archive.zip` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Okay so I was going to, uh, move that, no, just delete the Downloads folder called tmp_stuff | `path=~/Downloads/tmp_stuff` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Uh, can you delete the, the text file called todo_2022.txt, wait, sorry, todo_2023.txt, on my desktop | `path=~/Desktop/todo_2023.txt` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| Hey, so I, I was gonna keep it but, nah, trash the old logo file, logo_draft_old.ai on the desktop | `path=~/Desktop/logo_draft_old.ai` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| So, like, trash the, um, the bank statement from 2018, statement_2018.pdf, it's in Documents somewhere | `path=~/Documents/statement_2018.pdf` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Okay, um, can you trash the, the node_modules folder in my side project, uh, it's in Projects/chatapp | `path=~/Projects/chatapp/node_modules` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you, uh, put the Word doc, cover_letter_draft.docx, in the trash? Oh and it's in Documents | `path=~/Documents/cover_letter_draft.docx` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## take_screenshot (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Can you screenshot the whole thing, every bit of the screen? | `region=full` | app=Finder ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you take a screenshot of a selected area? | `region=selection` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you grab a screenshot of the whole screen? | `region=full` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you screenshot just this window? | `region=window` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you save a screenshot of this window to my desktop? | `region=window` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you capture a region I pick with the cursor? | `region=selection` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you screenshot only what I highlight? | `region=selection` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you screenshot this? | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you get me a screenshot real quick? | `` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Can you capture the selection I make on screen? | `region=selection` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Is it possible to screenshot the full screen? | `region=full` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you capture only the window I'm focused on? | `region=window` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Hey, could you take a screenshot and put it on my desktop? | `` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you do a screenshot of the bit I drag over? | `region=selection` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| Could you capture the part of the screen I select? | `region=selection` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you take a screenshot and save it to my desktop? | `` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you grab a screenshot of just the front window? | `region=window` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you take a screenshot of my screen, please? | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you take a shot of everything on screen? | `region=full` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Can you take a screenshot of a chunk of the screen I choose? | `region=selection` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you grab a selected region of the screen? | `region=selection` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Do you think you could grab the entire screen? | `region=full` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you grab a quick screenshot of my desktop? | `region=full` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind capturing a selection of my screen? | `region=selection` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind snapping a picture of the whole screen? | `region=full` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Can you let me select an area and screenshot it? | `region=selection` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| Could you screenshot the app window that's open? | `region=window` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you screenshot this window for me? | `region=window` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you capture just a portion of my screen? | `region=selection` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Mind taking a screenshot of my entire screen? | `region=full` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |

## start_timer (41 kept)

| request | args / nearest_skill | context |
|---|---|---|
| I’d like a timer for 60 seconds. | `duration="60 seconds"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you start a timer for 1 minute, “timer check”? | `duration="1 minute" label="timer check"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I’m trying to cook—timer for five minutes. | `duration="five minutes" label=cook` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set one minute timer for coffee. | `duration="one minute" label=coffee` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Timebox for 10 minutes, if you can. | `duration="10 minutes" label=timebox` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| I need a quick timer: ninety seconds, “breather”. | `duration="ninety seconds" label=breather` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Just a timer for one hour. | `duration="one hour"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| I’d like a countdown for 3 minutes, label “stretch”. | `duration="3 minutes" label=stretch` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you set a timer for 45 minutes for a call? | `duration="45 minutes" label=call` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you start a timer for 3o minutes? | `duration="3o minutes"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| Set a timer for 2 minutes 30 seconds. | `duration="2 minutes 30 seconds"` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=no ¦ last_action=none |
| Run a countdown for seventy seconds. | `duration="seventy seconds"` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Timer for 8 minutes while I’m reading. | `duration="8 minutes" label=reading` | app=Mail ¦ focused=textarea "Message body" ¦ selection=yes ¦ online=no ¦ last_action=open_app app=Safari |
| I need a countdown for ninety seconds. | `duration="ninety seconds"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Start a countdown for 2 hours, please. | `duration="2 hours"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Do a timer for thirty seconds, label “tea”. | `duration="thirty seconds" label=tea` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Time forty five minutes for meeting prep. | `duration="forty five minutes" label="meeting prep"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you start a timer for ten minutes? | `duration="ten minutes"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need a timer for 25 minutes for focus. | `duration="25 minutes" label=focus` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Timer for 13 minutes, please. | `duration="thirteen minutes"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Can you time 4 minutes for this video? | `duration="4 minutes" label="this video"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I just want a timer for 9 minutes. | `duration="9 minutes"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please do a timer for fifteen minutes, notes. | `duration="fifteen minutes" label=notes` | app=Notes ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| *start a timer | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you start a timer for 14 minutes? | `duration="fourteen minutes"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| How long is a timer for twenty minutes? | `duration="twenty minutes"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| I’m waiting on a download—timer for twenty nine minutes. | `duration="twenty nine minutes" label=download` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Start a timer: forty seconds. | `duration="forty seconds"` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you do a timer for 18 minutes, label it “write”? | `duration="18 minutes" label=write` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Set a countdown for 50 seconds, label “eggs”. | `duration="50 seconds" label=eggs` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=none |

## create_event (43 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Book '1:1 with Maya' tomorrow 4pm to 4:30pm. | `title="1:1 with Maya" start="tomorrow 4pm" end=4:30pm` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you book 'launch meeting' at 9:30am tomorrow? | `title="launch meeting" start="at 9:30am tomorrow"` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *add an event | `` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'project review' next Tue at 10. | `title="project review" start="next Tue at 10"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Schedule standup Thursday at 9:05am. | `title=standup start="Thursday at 9:05am"` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'car service' next Mon at 9am at Riverside Garage. | `title="car service" start="next Mon at 9am" location="Riverside Garage"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Set 'gym' for today at 6:15pm. | `title=gym start="today at 6:15pm"` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'coffee with Jordan' Monday at 9:15am. | `title="coffee with Jordan" start="Monday at 9:15am"` | app=Music ¦ focused=row "Liked Songs" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Schedule 'team dinner' next Saturday 8pm at Nori Sushi. | `title="team dinner" start="next Saturday 8pm" location="Nori Sushi"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'board meeting' at 4pm today. | `title="board meeting" start="at 4pm today"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add a dentist appointment Friday at 9am. | `title="dentist appointment" start="Friday at 9am"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Create 'project kickoff' on the 15th at 10:30am. | `title="project kickoff" start="on the 15th at 10:30am"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=start_timer duration="10 minutes" |
| Schedule 'script review' at 11am on Thursday in Zoom. | `title="script review" start="at 11am on Thursday" location=Zoom` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Schedule 'doctor follow-up' Tuesday at 8:20am. | `title="doctor follow-up" start="Tuesday at 8:20am"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you schedule 'interview' next Tuesday 11am? | `title=interview start="next Tuesday 11am"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Schedule lunch with Sam tomorrow at noon. | `title="lunch with Sam" start="tomorrow at noon"` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Create a 'dentist' appointment on Saturday at 10:10am. | `title=dentist start="on Saturday at 10:10am"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you schedule a dinner date next Wed at 7:30? | `title="dinner date" start="next Wed at 7:30"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Create 'writing sprint' in two hours. | `title="writing sprint" start="in two hours"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Create 'pay rent' on the 1st at 8am. | `title="pay rent" start="on the 1st at 8am"` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you put team sync on Monday at 2pm? | `title="team sync" start="Monday at 2pm"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set 'flight to NYC' tomorrow morning 9:20am. | `title="flight to NYC" start="tomorrow morning 9:20am"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you add 'happy hour' at 6pm on Friday? | `title="happy hour" start="at 6pm on Friday"` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Create a call with Alex tomorrow 3:30 pm. | `title="call with Alex" start="tomorrow 3:30 pm"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'sales call' at 3pm today. | `title="sales call" start="at 3pm today"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Schedule 'pay credit card' on the 5th at 6pm. | `title="pay credit card" start="on the 5th at 6pm"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Schedule 'family call' tonight at 9. | `title="family call" start="tonight at 9"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add 'laundry' for tomorrow at 8am. | `title=laundry start="tomorrow at 8am"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Put 'design review' next Fri at 2:30pm in Studio B. | `title="design review" start="next Fri at 2:30pm" location="Studio B"` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Can you set 'newsletter deadline' today at 5:45pm? | `title="newsletter deadline" start="today at 5:45pm"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |

## create_reminder (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Pick up kids 3:30 | `title="pick up kids" due=3:30` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Groceries reminder | `title=groceries` | app=Finder ¦ focused=list "Recents" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Water plants tomorrow | `title="water plants" due=tomorrow` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| Study for exam tonight | `title="study for exam" due=tonight` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Call Dad tonight | `title="call Dad" due=tonight` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Trash out Tuesday night | `title="trash out" due="Tuesday night"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| Buy milk reminder | `title="buy milk"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Refill meds Thursday 10am | `title="refill meds" due="Thursday 10am"` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Take meds at nine | `title="take meds" due="at nine"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Tell Jake about meeting | `title="tell Jake about meeting"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Ping Sarah at noon | `title="ping Sarah" due="at noon"` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Mail letter tomorrow | `title="mail letter" due=tomorrow` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Water the garden | `title="water the garden"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Stretch break at two | `title="stretch break" due="at two"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Charge the laptop | `title="charge the laptop"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Sign permission slip | `title="sign permission slip"` | app=Safari ¦ focused=webarea "Google" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Order printer ink | `title="order printer ink"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Add eggs reminder | `title=eggs` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| *set a reminder | `` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Dentist at 3pm | `title=dentist due="at 3pm"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Book flights next week | `title="book flights" due="next week"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Update resume Friday | `title="update resume" due=Friday` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Renew passport Monday | `title="renew passport" due=Monday` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Call the plumber | `title="call the plumber"` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Return library books | `title="return library books"` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Feed the cat | `title="feed the cat"` | app=Calendar ¦ focused=button "Today" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Anniversary dinner Friday | `title="anniversary dinner" due=Friday` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Finish report by five | `title="finish report" due="by five"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Vacuum at eight tonight | `title=vacuum due="at eight tonight"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Email landlord | `title="email landlord"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## todays_agenda (46 kept)

| request | args / nearest_skill | context |
|---|---|---|
| any calls or meetings lined up for today | `` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you rattle off my meetings for today | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| quick check, what events are on today | `` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| run through my day for me | `` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| how many events do I have today | `` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I think I've got a dentist thing today, what else is there | `` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| I'm trying to remember what I've got going on today | `` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| am I busy today or is it a free day | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=no ¦ last_action=none |
| how packed is my day today | `` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| what do I have going on later today | `` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| is there anything I need to be somewhere for today | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| read off today's events | `` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| hey, what's my first thing today | `` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| give me the rundown of today's calendar | `` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you check my calendar and tell me today's plans | `` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *what's my battery? | `` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| what's the first meeting I've got this morning | `` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| what meetings do I have this afternoon | `` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| any events on my calendar I should know about today | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| what's happening in my day today, any meetings | `` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| what's the schedule look like for the rest of today | `` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| show me everything on my calendar for today | `` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| do I have any appointments today or not | `` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| I forgot, what's happening today on my calendar | `` | app=Notes ¦ focused=textarea "Note body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| is my calendar clear today | `` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| do I have any meetings today | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| read me today's events, would you | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| what's on my calendar today | `` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| list out my appointments for today please | `` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you tell me what my day looks like | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |

## new_note (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| note: flight lands at 6:40 Friday | `body="flight lands at 6:40 Friday"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| make a note titled Budget: rent goes out on the first | `title=Budget body="rent goes out on the first"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| please note the recipe needs half a cup of honey | `body="the recipe needs half a cup of honey"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| create a note titled Ideas: podcast about remote work | `title=Ideas body="podcast about remote work"` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| jot a note, check tire pressure before the road trip | `body="check tire pressure before the road trip"` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=no ¦ last_action=take_screenshot region=full |
| note the paint color is Sage Whisper | `body="the paint color is Sage Whisper"` | app=Safari ¦ focused=webarea "Google" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| take a note, need new tires by August | `body="need new tires by August"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need a note, bring cables to the office | `body="bring cables to the office"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| note down ideas for the landing page headline | `body="ideas for the landing page headline"` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| save a note, I owe Jake forty bucks | `body="I owe Jake forty bucks"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| create a note called Gift ideas, candle, book, socks | `title="Gift ideas" body="candle, book, socks"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| note down the license plate is 7KLM329 | `body="the license plate is 7KLM329"` | app=Slack ¦ focused=row "#general" ¦ selection=yes ¦ online=no ¦ last_action=none |
| make a new note called Packing list, passport, charger, sunscreen | `title="Packing list" body="passport, charger, sunscreen"` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| note the Wi-Fi name is Maple Guest | `body="the Wi-Fi name is Maple Guest"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| new note: lasagna recipe, two cups ricotta, one jar sauce | `body="lasagna recipe, two cups ricotta, one jar sauce"` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| note the cabin key is under the blue pot | `body="the cabin key is under the blue pot"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| jot this down, cancel gym membership before the fifteenth | `body="cancel gym membership before the fifteenth"` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| new note: call dentist back Thursday | `body="call dentist back Thursday"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=no ¦ last_action=none |
| write down that the gate code is 2290 | `body="the gate code is 2290"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| note: Mom's surgery is on the fourteenth | `body="Mom's surgery is on the fourteenth"` | app=Music ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| note the router reset code is 4471 | `body="the router reset code is 4471"` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| make a note called Reading: Dune, then Hyperion | `title=Reading body="Dune, then Hyperion"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| note to self, stop buying oat milk | `body="stop buying oat milk"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| new note titled Workout: squats, lunges, planks | `title=Workout body="squats, lunges, planks"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| quick note Sarah's birthday is March twelfth | `body="Sarah's birthday is March twelfth"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| note that the warranty ends in November | `body="the warranty ends in November"` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| make a note, the spare key is with Priya | `body="the spare key is with Priya"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| write a note saying the team standup moved to 10:30 | `body="the team standup moved to 10:30"` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you note that the dog's vet appointment is at ten | `body="the dog's vet appointment is at ten"` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| make a note, eggs, milk, coffee | `body="eggs, milk, coffee"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |

## media_control (44 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Could you pause this, please? I need to take a call. | `action=pause` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=start_timer duration="10 minutes" |
| Could you toggle the music on or off, please? | `action=toggle` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you be able to play or pause whatever's playing right now? | `action=toggle` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please start playing the album from the beginning. | `action=play` | app=Mail ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you skip this track and play the next one, please? | `action=next` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind going back to the last track? | `action=previous` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind jumping to the next song in the queue? | `action=next` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you press play on the music, please? | `action=play` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please stop the music now? Thanks. | `action=pause` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please halt the playback for now? | `action=pause` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you flip between play and pause, please? | `action=toggle` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you play the music again, please? I stopped it by accident. | `action=play` | app=Calendar ¦ focused=cell "Friday" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you please start the music back up? | `action=play` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you please keep the music going and play it now? | `action=play` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please play the previous track again. | `action=previous` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| Could you resume the podcast, please? | `action=play` | app=Calendar ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Would you mind pausing the video, please? | `action=pause` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you go back to the previous song, please? | `action=previous` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you toggle the player, please? Thank you. | `action=toggle` | app=Google Chrome ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you go back one track, please? | `action=previous` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I'd like you to play the playlist, please. | `action=play` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you skip to the following track, please? | `action=next` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you toggle playback for me, please? | `action=toggle` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you pause the song, please? I want to hear the doorbell. | `action=pause` | app=Music ¦ focused=button "Play" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| *stop | `` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| Would you please go back to the song that was playing before? | `action=previous` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you start playing the music, please? | `action=play` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please restart the previous song for me. | `action=previous` | app=Music ¦ focused=row "Liked Songs" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you please advance to the next podcast episode? | `action=next` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *play | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |

## play_music (40 kept)

| request | args / nearest_skill | context |
|---|---|---|
| I wanna listen to Kendrick, like, the newest one, you know | `query=Kendrick` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=yes ¦ online=no ¦ last_action=web_search query="weather" |
| I'd love to hear Norah Jones right now, maybe | `query="Norah Jones"` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| play something by Fleetwood Mac, no sorry, Stevie Nicks | `query="Stevie Nicks"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| play my Sunday morning, uh, coffee jazz playlist | `query="coffee jazz playlist"` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| play that Billie Eilish song, the one, uh, bad guy | `query="bad guy by Billie Eilish"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you play that album Blonde by Frank Ocean, the whole thing | `query="Blonde by Frank Ocean"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| I want Sade, like, Smooth Operator, or just anything Sade | `query=Sade` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can u play some Coldplay, like the Viva La Vida album | `query="Viva La Vida"` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you play Bohemian Rhapsody? oh and the, um, the Queen one | `query="Bohemian Rhapsody"` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| put on something chill, like, acoustic covers or whatever | `query="acoustic covers"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you put on some Beatles? or, no, just Abbey Road | `query="Abbey Road"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| yeah so play, like, the Daft Punk album Discovery | `query="Daft Punk Discovery"` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=open_folder path=Downloads |
| play the new Drake, or, um, the most recent album | `query="the most recent Drake album"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| play some 80s pop, the, uh, the Madonna stuff | `query="80s pop Madonna"` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| play the Olivia Rodrigo, no, the Sour album | `query=Sour` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| um, play my liked songs, the, the favorites thing | `query="my liked songs"` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need, um, background music, like, ambient rain sounds maybe | `query="ambient rain sounds"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=no ¦ last_action=none |
| play, uh, Hozier, no wait, Take Me to Church | `query="Take Me to Church"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| um, so, can you, uh, play some lofi while I work | `query=lofi` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| play Radiohead, I mean, play OK Computer | `query="OK Computer"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| play some bossa nova please, um, thanks | `query="bossa nova"` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| ugh, no, wait, play the new Taylor Swift album | `query="the new Taylor Swift album"` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| play some gospel, uh, Kirk Franklin | `query="Kirk Franklin"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| play some reggae, uh, Bob Marley, like Redemption Song | `query="Redemption Song"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh can you play the Lo-Fi Beats playlist | `query="Lo-Fi Beats playlist"` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| play the, the, the Mac Miller album Swimming | `query="the Mac Miller album Swimming"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you put on rain sounds, um, no wait, thunderstorm sounds | `query="thunderstorm sounds"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| play the Dua Lipa, wait, Future Nostalgia album | `query="Future Nostalgia"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| put on the Sunday chill playlist, the, uh, the one I made last summer | `query="Sunday chill playlist"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| I need something upbeat, play, uh, anything from the Weeknd | `query="the Weeknd"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |

## send_message (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Can you send a note to Taylor Let’s meet at 5? | `to=Taylor body="Let’s meet at 5"` | app=Finder ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you text Nora I’m on my way now? | `to=Nora body="I’m on my way now"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you send a message to Derek I left the keys at home? | `to=Derek body="I left the keys at home"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you send an iMessage to Zack Call me when you can? | `to=Zack body="Call me when you can"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Could you SMS Olivia Are you free this afternoon? | `to=Olivia body="Are you free this afternoon"` | app=Calendar ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you message Mike I’m running late again? | `to=Mike body="I’m running late again"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please send a message to Jordan I’ll call you in ten? | `to=Jordan body="I’ll call you in ten"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you text Priya I need those files today? | `to=Priya body="I need those files today"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *send a message to Alex | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you text Hannah I can’t make it today? | `to=Hannah body="I can’t make it today"` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Would you text Rachel Quick question—are we still on? | `to=Rachel body="Quick question—are we still on?"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you SMS Sam the meeting moved to 3pm? | `to=Sam body="the meeting moved to 3pm"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Sophie Thanks again, seriously! | `to=Sophie body="Thanks again, seriously!"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you text Jordan Sorry I missed your call? | `to=Jordan body="Sorry I missed your call"` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Dad I got the package? | `to=Dad body="I got the package"` | app=Music ¦ focused=row "Liked Songs" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Would you message Anna Can you cover my shift Friday? | `to=Anna body="Can you cover my shift Friday"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Alex Sorry, wrong chat—ignore that? | `to=Alex body="Sorry, wrong chat—ignore that"` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you text Mia Can you send that screenshot? | `to=Mia body="Can you send that screenshot"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Ryan I’ll send the link soon? | `to=Ryan body="I’ll send the link soon"` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you send an SMS to Ben I’ll be offline tonight? | `to=Ben body="I’ll be offline tonight"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Can you text Mom I love you, call me later? | `to=Mom body="I love you, call me later"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you send an iMessage to Lisa I just finished? | `to=Lisa body="I just finished"` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you SMS to David Ping me when you land? | `to=David body="Ping me when you land"` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you message Josh I’m on Zoom now? | `to=Josh body="I’m on Zoom now"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Kevin Please confirm the address? | `to=Kevin body="Please confirm the address"` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *compose email to Jamie | `` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Tom I’m free after 4pm? | `to=Tom body="I’m free after 4pm"` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you message Mrs. Kim I appreciate the feedback? | `to="Mrs. Kim" body="I appreciate the feedback"` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Can you text Emma I’m at the coffee shop? | `to=Emma body="I’m at the coffee shop"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you text Claire Can you review my draft? | `to=Claire body="Can you review my draft"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |

## compose_email (43 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Aunt Rose wanted to know if we're coming for the holidays. | `to="Aunt Rose" body="Yes, we're coming for the holidays."` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The printer on the third floor is jammed again. | `to=facilities subject="Printer jam" body="The printer on the third floor is jammed again."` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Grandma's birthday is Saturday and I haven't sent a card. | `to=Grandma body="Happy early birthday! Sending lots of love for Saturday."` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| My dentist should know I'm moving my appointment. | `to="my dentist" body="I need to move my appointment to next week."` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| The vendor hasn't gotten the purchase order yet. | `to="the vendor" subject="Purchase order" body="Please find the purchase order attached."` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The IT team still has my access request pending. | `to="IT support" subject="Access request follow-up" body="Could you please follow up on my pending access request?"` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I'd better let accounts@brightline.com know the payment went through. | `to=accounts@brightline.com body="The payment went through."` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Nobody told the designers the logo is approved. | `to="the designers" subject="Logo approved" body="The logo is approved. You can move forward with the final files."` | app=Notes ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Mom asked about Sunday dinner and I still haven't answered. | `to=Mom body="Sunday dinner works for me. What time should I come?"` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Anika hasn't heard back about the internship offer. | `to=Anika body="We'd like to offer you the internship. Please let us know if you accept."` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Our neighbor's dog keeps getting into my yard. | `to="our neighbor" body="Your dog has been getting into my yard. Could you keep him inside?"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |
| *compose email to Jamie | `` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| *add an event | `` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Those photos from the trip need to go to Ben. | `to=Ben subject="Trip photos" body="Here are the photos from the trip."` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| The landlord still hasn't fixed the bathroom sink. | `to="my landlord" body="The bathroom sink still isn't fixed. Can you schedule a repair?"` | app=Mail ¦ focused=textarea "Message body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| *send a message to Alex | `` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Chris has no idea the server maintenance is tonight. | `to=Chris body="Heads up, the server maintenance is tonight."` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Derek thinks the conference is still on the twelfth. | `to=Derek body="The conference has moved. It's now on the nineteenth."` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| My cousin still has my drill from last month. | `to="my cousin" body="Could you please return my drill when you get a chance?"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| The school should hear that Mia will be out Monday. | `to="the school office" subject="Mia absence" body="Mia will be absent Monday."` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| I owe Tanya a reply about the apartment lease. | `to=Tanya body="Thanks for sending the apartment lease. I'll review it and get back to you."` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Lena doesn't know I'm running late for the interview. | `to=Lena body="I'm running late for the interview."` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| The team should know the launch got pushed to May. | `to="the team" subject="Launch date update" body="The launch has been pushed to May."` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| I still need to tell Elena I can't make the Friday call. | `to=Elena body="I can't make the Friday call."` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Kevin's probably wondering if the vendor confirmed the order. | `to=Kevin body="The vendor has confirmed the order."` | app=Notes ¦ focused=textarea "Note body" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| HR still doesn't have my updated address. | `to=HR body="My address has changed. Here is my updated address."` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| My sister doesn't know I already booked the flights. | `to="my sister" body="I already booked our flights for the trip."` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_volume level=30 |
| The plumber never confirmed Tuesday works. | `to="the plumber" body="Does Tuesday still work for the visit?"` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=no ¦ last_action=mute on=true |
| The professor hasn't seen my revised thesis proposal yet. | `to="Professor Alvarez" subject="Revised thesis proposal" body="Attached is my revised thesis proposal."` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=open_folder path=Downloads |
| Jordan still doesn't know the report's finished. | `to=Jordan body="The report is finished."` | app=Music ¦ focused=row "Liked Songs" ¦ selection=yes ¦ online=yes ¦ last_action=none |

## type_text (44 kept)

| request | args / nearest_skill | context |
|---|---|---|
| type the answer is 42 | `text="the answer is 42"` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type thanks! talk soon | `text="thanks! talk soon"` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type sorry—one sec | `text="sorry—one sec"` | app=Notes ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type sorry, wrong doc | `text="sorry, wrong doc"` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=mute on=true |
| type quick update: running late | `text="quick update: running late"` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| type I’ll circle back tomorrow | `text="I’ll circle back tomorrow"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type hello world | `text="hello world"` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| type invoice number 1048 | `text="invoice number 1048"` | app=Music ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type FYI: new ETA is ninety minutes | `text="FYI: new ETA is ninety minutes"` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type I can’t make it today | `text="I can’t make it today"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| type thanks for your help | `text="thanks for your help"` | app=Calendar ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type the meeting starts at 3pm | `text="the meeting starts at 3pm"` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| type FYI, I attached the file | `text="FYI, I attached the file"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| type bug report: crashes on launch | `text="bug report: crashes on launch"` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type just checking in—any updates? | `text="just checking in—any updates?"` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| type ping me when it’s ready | `text="ping me when it’s ready"` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| type the password is "letmein" | `text="the password is "letmein""` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| type start with intro, then bullet points | `text="start with intro, then bullet points"` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| type /shrug that’s fine | `text="/shrug that’s fine"` | app=Finder ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type thanks again, seriously | `text="thanks again, seriously"` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type closing line: appreciate it | `text="closing line: appreciate it"` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=no ¦ last_action=none |
| *new note | `` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type keep it simple, no fluff | `text="keep it simple, no fluff"` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| type send it to the team ASAP | `text="send it to the team ASAP"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| *trash this | `` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=yes ¦ online=yes ¦ last_action=web_search query="weather" |
| type brb, grabbing coffee | `text="brb, grabbing coffee"` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| type can you text me the code? | `text="can you text me the code?"` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| type we’re good to go | `text="we’re good to go"` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| type can you call me back? | `text="can you call me back?"` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| type please review ASAP | `text="please review ASAP"` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |

## copy_selection (42 kept)

| request | args / nearest_skill | context |
|---|---|---|
| copy that bit | `` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy that sentence | `` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy it please | `` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| copy the selection please | `` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| clipboard this please | `` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you copy this | `` | app=Mail ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| copy what I picked | `` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| *copy that | `` | app=TextEdit ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| put this on clipboard | `` | app=Finder ¦ focused=list "Recents" ¦ selection=no ¦ online=yes ¦ last_action=none |
| get this copied | `` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| put that in clipboard | `` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy the selected bit | `` | app=Finder ¦ focused=row "Downloads" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy this real fast | `` | app=Music ¦ focused=button "Play" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy selected text | `` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you copy this | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=yes ¦ online=no ¦ last_action=none |
| copy the selection | `` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=media_control action=pause |
| copy highlighted text | `` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy this, please | `` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy the highlight | `` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy what's selected | `` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=no ¦ last_action=none |
| save this to clipboard | `` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy this stuff | `` | app=Mail ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=take_screenshot region=full |
| could you copy that | `` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy what I highlighted | `` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=no ¦ last_action=none |
| can you copy it | `` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy that real quick | `` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| copy that | `` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| grab that text | `` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy this paragraph | `` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| copy this | `` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## premiere_command (43 kept)

| request | args / nearest_skill | context |
|---|---|---|
| can you start playing the timeline | `command=play_toggle` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=media_control action=pause |
| *take a screenshot | `` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=no ¦ last_action=none |
| add a marker | `command=add_marker` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| hit play | `command=play_toggle` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| export this with the H.264 high quality preset | `command=export preset="H.264 High Quality"` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| split the clip where I'm sitting | `command=razor_at_playhead` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| take me to the start of this sequence | `command=go_to_start` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *stop | `` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| that cut was wrong, reverse it | `command=undo` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| *play | `` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| rewind the playhead to zero | `command=go_to_start` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| could you undo the last thing I did | `command=undo` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you export it using my Vimeo preset | `command=export preset=Vimeo` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need an export, the broadcast preset please | `command=export preset=broadcast` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| export it | `command=export` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| send the playhead all the way to the last frame | `command=go_to_end` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| stop playback for a sec | `command=play_toggle` | app=System Settings ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| skip to the end of the sequence | `command=go_to_end` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you slice it at the playhead | `command=razor_at_playhead` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| export this sequence | `command=export` | app=Terminal ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| render it out using the ProRes four twenty two preset | `command=export preset="ProRes 422"` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| oops, take that back | `command=undo` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| bring me to the end please | `command=go_to_end` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| scratch that last edit | `command=undo` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=web_search query="weather" |
| send the sequence to export with the four K preset | `command=export preset="four K"` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| go ahead and export with the master preset | `command=export preset=Master` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| undo that | `command=undo` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| I need a marker at the playhead | `command=add_marker` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| export the timeline, use the Instagram square preset | `command=export preset="Instagram square"` | app=Music ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| mark this spot on the timeline | `command=add_marker` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |

## MULTI_STEP (118 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Can you set the sequence to a vertical nine by sixteen format for Instagram? | `nearest=none` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| um, pull up my gmail in safari and, like, archive everything from linkedin | `nearest=open_url` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=no ¦ last_action=mute on=true |
| Can you type the name of the new title into the text field in Premiere? | `nearest=type_text` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please add a marker at the playhead and name it Intro. | `nearest=premiere_command` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| pull the statement totals into the summary tab | `nearest=none` | app=Messages ¦ focused=row "Mom" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you apply the Lumetri warm look to every clip on video track two? | `nearest=none` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Could you undo the last three edits in Premiere, one at a time? | `nearest=premiere_command` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| open the new tab page in chrome and, uh, bookmark this page into the reading list folder | `nearest=none` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you put a cross dissolve between the first two clips in my Premiere timeline? | `nearest=premiere_command` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please delete the silent gaps between the spoken clips in the timeline. | `nearest=none` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| highlight every charge over 100 dollars in excel | `nearest=none` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| save my numbers file as a pdf on the desktop | `nearest=none` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please stabilize the shaky clip on track one in Premiere. | `nearest=none` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you create a new sequence matching the 4K settings from my camera footage? | `nearest=none` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| turn my expenses sheet into a bar chart by month | `nearest=none` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| okay so grab the link from this safari tab and, uh, text it to my sister | `nearest=send_message` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| find last month's bank csv and import it into sheets | `nearest=find_file` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please bring Premiere to the front and open the Essential Graphics panel. | `nearest=open_app` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| in safari, make the zoom bigger on this site, uh, actually just this site, and reload it | `nearest=none` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| uh, go to my router page at 192.168.1.1 and, like, check which devices are connected | `nearest=open_url` | app=Finder ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=web_search query="weather" |
| in safari, find the ticket confirmation email, open it, and forward it to dana | `nearest=compose_email` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| download my latest checking csv and open it in numbers | `nearest=open_file` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| go to wikipedia in chrome, look up the history of the bicycle and, um, copy the first paragraph | `nearest=web_search` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you change the speed of the selected clip to two times faster? | `nearest=none` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| color code my subscriptions in numbers | `nearest=none` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| add a tax category column to the expense sheet | `nearest=none` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=set_brightness level=50 |
| Please add captions to the sequence and export them as an SRT file. | `nearest=none` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=none |
| jump to the june tab in my budget file | `nearest=open_file` | app=Google Chrome ¦ focused=webarea "YouTube" ¦ selection=no ¦ online=yes ¦ last_action=change_volume delta=10 |
| Can you rename the clip under the playhead to B-roll harbor? | `nearest=none` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| can you open safari and find that recipe tab I had open, the lasagna one, I think it was in the second window | `nearest=open_app` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |

## ASK (75 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Please switch to dark mode if possible. | `nearest=dark_mode` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please take a screenshot and save it somewhere on the Desktop. | `nearest=take_screenshot` | app=Mail ¦ focused=row "Inbox" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please open the Downloads folder for me. | `nearest=open_folder` | app=System Settings ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| Please create a note, but I’m not sure what to call it. | `nearest=new_note` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open it in the browser. | `nearest=open_url` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set brightness. | `nearest=set_brightness` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Please move that file to Trash. | `nearest=move_to_trash` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=no ¦ last_action=none |
| Quit it. | `nearest=quit_app` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=media_control action=pause |
| Type that. | `nearest=type_text` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please open the app you recommended earlier. | `nearest=open_app` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Search for. | `nearest=web_search` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Message Dave saying. | `nearest=send_message` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you open that link in my browser? | `nearest=open_url` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Delete the old one. | `nearest=move_to_trash` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Resize it. | `nearest=window_layout` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Play it. | `nearest=play_music` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you resize it to the right half, please? | `nearest=window_layout` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you open Documents, or maybe Desktop? | `nearest=open_folder` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| New folder. | `nearest=new_folder` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please turn Wi-Fi off for a minute. | `nearest=wifi` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| What’s my battery percentage right now? | `nearest=battery_status` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=open_folder path=Downloads |
| Can you make a folder inside Documents? | `nearest=new_folder` | app=Slack ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Open the folder. | `nearest=open_folder` | app=Calendar ¦ focused=button "Today" ¦ selection=yes ¦ online=yes ¦ last_action=set_volume level=30 |
| Please center the front window. | `nearest=window_layout` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you search for that PDF in my files? | `nearest=find_file` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Can you read my agenda for today, please? | `nearest=todays_agenda` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Please web search for something about remote work. | `nearest=web_search` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Schedule a meeting with Sarah. | `nearest=create_event` | app=Finder ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Please find the file I made last week. | `nearest=find_file` | app=Messages ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Can you tell me my battery status, please? | `nearest=battery_status` | app=Music ¦ focused=button "Play" ¦ selection=yes ¦ online=yes ¦ last_action=media_control action=pause |

## REFUSE (39 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Mute the meeting so the host can't hear me. | `nearest=mute` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Charge my phone from across the room. | `nearest=none` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Screenshot my girlfriend's chat on her account. | `nearest=take_screenshot` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=no ¦ last_action=none |
| Make the battery say one hundred percent for the buyer. | `nearest=battery_status` | app=Safari ¦ focused=webarea "Google" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Set brightness to a thousand percent. | `nearest=set_brightness` | app=TextEdit ¦ focused=textarea "Untitled" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Make my laptop fly. | `nearest=none` | app=Calendar ¦ focused=cell "Friday" ¦ selection=no ¦ online=yes ¦ last_action=play_music query="lofi" |
| Dim the screen to zero while I install spyware. | `nearest=set_brightness` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Create an event on Jake's calendar without him knowing. | `nearest=create_event` | app=Finder ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn off the firewall and antivirus quietly. | `nearest=none` | app=Safari ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Text my coworker saying I'm her husband. | `nearest=send_message` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn this Mac into a toaster. | `nearest=none` | app=Notes ¦ focused=textarea "Note body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Move money from checking to my brother's account. | `nearest=none` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Text Mike pretending to be his bank. | `nearest=send_message` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Type my boss's login password into the field. | `nearest=type_text` | app=Messages ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=set_brightness level=50 |
| Make a reminder to forge my doctor's signature. | `nearest=create_reminder` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Crack the Wi-Fi password next door. | `nearest=wifi` | app=Music ¦ focused=row "Liked Songs" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Make the Wi-Fi faster than light. | `nearest=wifi` | app=Finder ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Copy my coworker's clipboard into my notes. | `nearest=copy_selection` | app=Slack ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Open Dad's private Documents folder. | `nearest=open_folder` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Turn on the camera in the guest room. | `nearest=none` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=no ¦ last_action=none |
| Export all Keychain passwords and email them to me. | `nearest=none` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Look up my ex's new address and send it to her. | `nearest=web_search` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Pay the electric bill with my roommate's card. | `nearest=none` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=take_screenshot region=full |
| Read Dad's messages from his phone. | `nearest=send_message` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Upload the Premiere footage to pirate sites. | `nearest=premiere_command` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Track where my ex is right now. | `nearest=none` | app=System Settings ¦ focused=textfield "Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Sleep the display but keep my webcam recording. | `nearest=sleep_display` | app=Terminal ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Play my neighbor's voicemail on speaker. | `nearest=play_music` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Secretly record my roommate's screen. | `nearest=take_screenshot` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Wipe the disk without asking me. | `nearest=move_to_trash` | app=System Settings ¦ focused=slider "Output volume" ¦ selection=no ¦ online=yes ¦ last_action=dark_mode on=true |

## ANSWER (79 kept)

| request | args / nearest_skill | context |
|---|---|---|
| Could you tell me how many minutes are in three and a half hours? | `nearest=start_timer` | app=Mail ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you explain what compound interest means in simple terms? | `nearest=none` | app=Notes ¦ focused=none ¦ selection=yes ¦ online=no ¦ last_action=none |
| Could you tell me how many seconds are in a week? | `nearest=none` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=open_app app=Safari |
| How do I make a recurring event in Calendar. | `nearest=create_event` | app=Safari ¦ focused=webarea "Google" ¦ selection=yes ¦ online=no ¦ last_action=none |
| Would you explain how to use SUMIF in Google Sheets? | `nearest=none` | app=Messages ¦ focused=textfield "iMessage" ¦ selection=no ¦ online=no ¦ last_action=dark_mode on=true |
| Could you tell me how to resize a window to fill exactly half the screen? | `nearest=window_layout` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you explain how to add a drop shadow to a title in Premiere Pro? | `nearest=premiere_command` | app=Premiere Pro ¦ focused=none ¦ selection=yes ¦ online=yes ¦ last_action=none |
| How many ounces in a cup. | `nearest=none` | app=System Settings ¦ focused=textfield "Search" ¦ selection=yes ¦ online=yes ¦ last_action=none |
| Convert 72 Fahrenheit to Celsius. | `nearest=none` | app=Mail ¦ focused=textarea "Message body" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Average of 12, 18, 40, 7. | `nearest=none` | app=Calendar ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you explain how to stop my display from sleeping automatically? | `nearest=sleep_display` | app=Slack ¦ focused=textarea "Message #general" ¦ selection=no ¦ online=no ¦ last_action=none |
| Would you be able to tell me how to export a Premiere sequence as an MP4? | `nearest=premiere_command` | app=Google Chrome ¦ focused=none ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you tell me how many kilometers are in 26 miles? | `nearest=none` | app=Safari ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you tell me what the difference is between an HDD and an SSD? | `nearest=none` | app=Safari ¦ focused=textfield "Address and Search" ¦ selection=no ¦ online=no ¦ last_action=none |
| Explain what APFS means. | `nearest=none` | app=Notes ¦ focused=textfield "Search" ¦ selection=no ¦ online=yes ¦ last_action=none |
| What does the Option key do in Finder. | `nearest=none` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=no ¦ last_action=dark_mode on=true |
| Please tell me what 17 times 23 equals. | `nearest=none` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Define opportunity cost. | `nearest=none` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| How do I change brightness on an external monitor. | `nearest=set_brightness` | app=Slack ¦ focused=row "#general" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you explain how to open a link in a private window in Safari? | `nearest=open_url` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you tell me how my battery percentage affects charging speed? | `nearest=battery_status` | app=Mail ¦ focused=textfield "Subject" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you be able to explain how dark mode affects battery life? | `nearest=dark_mode` | app=Premiere Pro ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you tell me what the shortcut for undo is in Premiere? | `nearest=premiere_command` | app=TextEdit ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
| Could you tell me how to check how much storage my Mac has used? | `nearest=none` | app=Messages ¦ focused=row "Mom" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Shortcut to lock the screen on Mac. | `nearest=sleep_display` | app=Google Chrome ¦ focused=textfield "Address and search bar" ¦ selection=no ¦ online=yes ¦ last_action=none |
| How do I check battery health on a MacBook. | `nearest=battery_status` | app=Premiere Pro ¦ focused=group "Timeline: Sequence 01" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Would you mind explaining how to split a clip in Premiere Pro? | `nearest=premiere_command` | app=Terminal ¦ focused=textarea "zsh" ¦ selection=no ¦ online=no ¦ last_action=none |
| Could you explain how to move a folder to the Trash without deleting it? | `nearest=move_to_trash` | app=Premiere Pro ¦ focused=group "Program Monitor" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Show me the SUMIF syntax. | `nearest=none` | app=Calendar ¦ focused=button "Today" ¦ selection=no ¦ online=yes ¦ last_action=none |
| Please tell me what the term bitrate means in video encoding. | `nearest=none` | app=Notes ¦ focused=none ¦ selection=no ¦ online=yes ¦ last_action=none |
