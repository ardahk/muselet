"""Context sampling for route items (SPEC 1.3)."""

from __future__ import annotations

import random

from muselet_train.route_render import RouteContext

APPS = [
    "Finder", "Safari", "Google Chrome", "Notes", "Mail", "Messages", "Calendar", "Music",
    "Premiere Pro", "TextEdit", "System Settings", "Terminal", "Slack",
]
FOCUSED = {
    "Finder": ['textfield "Search"', 'row "Downloads"', 'list "Recents"'],
    "Safari": ['textfield "Address and Search"', 'webarea "Google"'],
    "Google Chrome": ['textfield "Address and search bar"', 'webarea "YouTube"'],
    "Notes": ['textarea "Note body"', 'textfield "Search"'],
    "Mail": ['textarea "Message body"', 'row "Inbox"', 'textfield "Subject"'],
    "Messages": ['textfield "iMessage"', 'row "Mom"'],
    "Calendar": ['button "Today"', 'cell "Friday"'],
    "Music": ['button "Play"', 'row "Liked Songs"'],
    "Premiere Pro": ['group "Timeline: Sequence 01"', 'group "Program Monitor"'],
    "TextEdit": ['textarea "Untitled"'],
    "System Settings": ['textfield "Search"', 'slider "Output volume"'],
    "Terminal": ['textarea "zsh"'],
    "Slack": ['textarea "Message #general"', 'row "#general"'],
}
LAST_ACTIONS = [
    "set_volume level=30", "change_volume delta=10", "mute on=true", "set_brightness level=50",
    "open_app app=Safari", "media_control action=pause", "play_music query=\"lofi\"",
    "start_timer duration=\"10 minutes\"", "web_search query=\"weather\"", "dark_mode on=true",
    "take_screenshot region=full", "open_folder path=Downloads",
]


def sample_context(rng: random.Random, app: str | None = None, selection: bool | None = None,
                   online: bool | None = None, last_action: str | None = "__sample__") -> RouteContext:
    app = app or rng.choice(APPS)
    focused = rng.choice(FOCUSED.get(app, [])) if FOCUSED.get(app) and rng.random() < 0.6 else "none"
    if selection is None:
        selection = rng.random() < 0.15
    if online is None:
        online = rng.random() < 0.90
    if last_action == "__sample__":
        last_action = rng.choice(LAST_ACTIONS) if rng.random() < 0.15 else None
    return RouteContext(app=app, focused=focused, selection=selection, online=online,
                        last_action=last_action)
