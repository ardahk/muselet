"""Short mascot copy (<= 12 words) for skill success and failure (ux-3, ux-8).
Names the object, never shows raw skill ids; failures give one next step."""

import os
import re


def _cap(s: str, n: int = 12) -> str:
    w = s.split()
    return s if len(w) <= n else " ".join(w[:n])


def _base(p) -> str:
    p = str(p or "").rstrip("/")
    return os.path.basename(p) or p


def _onoff(v) -> str:
    return "on" if v in (True, "true", "on", 1) else "off"


def _dur(v) -> str:
    try:
        s = int(float(v))
    except (TypeError, ValueError):
        return str(v)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    parts = [f"{h} h" if h else "", f"{m} min" if m else "",
             f"{sec} s" if sec else ""]
    return " ".join(p for p in parts if p) or "0 s"


def human(name: str) -> str:
    return name.replace("_", " ")


_MEDIA = {"play": "Playing", "pause": "Paused", "next": "Next track",
          "previous": "Previous track", "stop": "Stopped"}


def success_text(name: str, args: dict, result=None) -> str:
    a = args or {}
    if isinstance(result, str) and result.strip() and \
            len(result.split()) <= 12 and name in (
                "battery_status", "todays_agenda", "find_file"):
        return result.strip()
    v = {
        "set_volume": lambda: f"Volume {a.get('level')}",
        "change_volume": lambda: "Volume " + (
            "down" if str(a.get("delta", "")).startswith("-") else "up"),
        "mute": lambda: "Muted" if _onoff(a.get("on")) == "on" else "Unmuted",
        "set_brightness": lambda: f"Brightness {a.get('level')}",
        "dark_mode": lambda: f"Dark mode {_onoff(a.get('on'))}",
        "wifi": lambda: f"Wi-Fi {_onoff(a.get('on'))}",
        "bluetooth": lambda: f"Bluetooth {_onoff(a.get('on'))}",
        "sleep_display": lambda: "Display sleeping",
        "battery_status": lambda: "Battery checked",
        "open_app": lambda: f"Opened {a.get('app')}",
        "quit_app": lambda: f"Quit {a.get('app')}",
        "hide_app": lambda: f"Hid {a.get('app')}",
        "window_layout": lambda: f"Windows {a.get('layout')}",
        "open_url": lambda: "Opened " + re.sub(
            r"^https?://(www\.)?", "", str(a.get("url", ""))).split("/")[0],
        "web_search": lambda: f'Searching "{a.get("query")}"',
        "open_folder": lambda: f"Opened {_base(a.get('path'))}",
        "find_file": lambda: f'Looking for "{a.get("query")}"',
        "open_file": lambda: f"Opened {_base(a.get('path'))}",
        "new_folder": lambda: f'Created folder "{a.get("name")}"',
        "move_to_trash": lambda: f"Moved {_base(a.get('path'))} to Trash",
        "take_screenshot": lambda: "Screenshot saved",
        "start_timer": lambda: f"Timer set for {_dur(a.get('duration'))}",
        "create_event": lambda: f"Added {a.get('title')} to Calendar",
        "create_reminder": lambda: f"Reminder set: {a.get('title')}",
        "todays_agenda": lambda: "Here's today",
        "new_note": lambda: "Note saved" + (
            f": {a['title']}" if a.get("title") else ""),
        "media_control": lambda: _MEDIA.get(str(a.get("action")), "Done"),
        "play_music": lambda: f"Playing {a.get('query')}",
        "send_message": lambda: f"Sent to {a.get('to')}",
        "compose_email": lambda: f"Email to {a.get('to')} is ready",
        "type_text": lambda: "Typed it",
        "copy_selection": lambda: "Copied",
        "premiere_command": lambda: f"Premiere: {a.get('command')}",
        "lock_screen": lambda: "Locked",
        "empty_trash": lambda: "Trash emptied",
    }.get(name)
    s = v() if v else "Done"
    return _cap("Done" if "None" in s else s)


def _obj(a: dict) -> str:
    for k in ("to", "app", "path", "title", "query", "name"):
        if a.get(k):
            return _base(a[k]) if k == "path" else str(a[k])
    return ""


def fail_text(name: str, args: dict, error: str = "") -> str:
    e, obj = (error or "").lower(), _obj(args or {})
    if e == "not_frontmost":
        s = "Opened it, but it didn't come to the front"
    elif re.search(r"not installed|no application|can't find app|unknown app", e):
        s = f"{obj or 'That app'} isn't installed. Try another app?"
    elif re.search(r"not found|no such|couldn't find|does not exist|no match|"
                   r"unknown contact", e):
        s = f"Couldn't find {obj or 'that'}. Check the name?"
    elif re.search(r"permission|not authori[sz]ed|not allowed|denied|tcc", e):
        s = "I need permission. Check Privacy & Security settings."
    elif re.search(r"timed? ?out", e):
        s = "That took too long. Try again?"
    elif re.search(r"disconnected|not connected", e):
        s = "The Muselet app isn't connected. Restart it?"
    else:
        s = f"Couldn't {human(name)}. Try saying it differently?"
    return _cap(s)
