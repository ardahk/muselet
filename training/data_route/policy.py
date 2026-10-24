"""Routing policy shown to judges, the adjudicator and generators (catalog v3). The first block is cloud A's
it3gen.POLICY verbatim (the policy route_v2 gold was judged under); the second adds the hard boundaries of the
it2 weak labels."""

from muselet_train.it3gen import POLICY as V3_POLICY

BOUNDARIES = """Hard boundaries:
- Channel: email (compose_email/draft_email) vs text message (send_message). If the words do not say email or text/message/iMessage, an email app frontmost (Mail, Gmail) means email; otherwise a named person is send_message.
- Indirect needs are valid skill requests when one skill clearly fits ("I can't hear anything" -> change_volume, "it's way too bright" -> set_brightness). ASK only when a required detail is missing or several options fit equally well.
- media_control: play / pause / resume / next / previous of whatever is playing (Music, Spotify, a video). premiere_command: commands on the Premiere Pro sequence (razor at playhead, add marker, play/stop the timeline, undo, export, go to start/end); play/pause/undo with Premiere Pro frontmost is premiere_command. Playing a named song, artist or playlist is play_music.
- open_folder: open a known folder (Downloads, Desktop, a path) in Finder. open_file: open one specific, identifiable file with its app. find_file: search for files when the location is unknown ("find", "where is", "look for", "any pdfs about ..."). Opening an app is open_app.
- set_brightness: display brightness, absolute or relative ("dimmer", "brighter", "full brightness"). dark_mode: light/dark appearance. set_volume: absolute volume level; change_volume: relative volume step ("louder", "a bit quieter"); mute: mute/unmute.
- Deleting or trashing the user's own files or emptying the trash is a skill (the app confirms), not REFUSE.
- web_search: needs the web (news, weather, prices, scores, looking something up online). ANSWER: the assistant can answer itself (math, conversions, definitions, how-to)."""

POLICY = V3_POLICY + "\n" + BOUNDARIES
