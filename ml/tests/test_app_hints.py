import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
from brain import cli
from brain.app_hints import (
    AppHint,
    load_hints,
    match_hints,
    open_ended_redirect,
    render_hints,
)
from brain.planner import Planner


def test_app_hint_matching_and_redirects():
    assert [hint.id for hint in match_hints("play jazz on spotify")] == [
        "spotify", "search_then_act"]
    assert [hint.id for hint in match_hints("directions to SFO")] == [
        "apple_maps"]
    assert [hint.id for hint in match_hints("open spotify")] == ["spotify"]
    assert [hint.id for hint in match_hints(
        "play some jazz", app="Spotify")] == ["spotify", "search_then_act"]
    assert open_ended_redirect("open_url", "open spotify", "safe") is None
    assert open_ended_redirect(
        "todays_agenda", "what's on my calendar today", None) is None
    assert open_ended_redirect(
        "play_music", "play jazz on spotify", None).id == "spotify"
    assert open_ended_redirect(
        "create_reminder", "add a reminder to call mom tomorrow at 5",
        None) is None
    assert open_ended_redirect(
        "find_file", "rename report.txt to final.txt", None).id == "rename_files"
    assert open_ended_redirect(
        "send_message", "send this in Slack", "confirm") is None
    assert open_ended_redirect(
        "open_url", "add usb-c cable to my amazon cart", "safe").id == "amazon"


def test_app_hint_order_limit_and_generic_selection():
    hints = [
        AppHint("app-first", ("spotify",), frozenset(), ("app",)),
        AppHint("goal-first", ("jazz",), frozenset(), ("goal",)),
        AppHint("third", ("music",), frozenset(), ("third",)),
        AppHint("search_then_act", ("play",), frozenset(), ("generic",), True),
    ]
    assert [hint.id for hint in match_hints(
        "play jazz", "Spotify", hints=hints, k=1)] == [
            "goal-first", "search_then_act"]
    assert [hint.id for hint in match_hints(
        "play something", "Spotify", hints=hints, k=2)] == [
            "app-first", "search_then_act"]


def test_app_hint_rendering_truncates_at_tip_boundary():
    first = "a" * 1050
    second = "b" * 200
    hint = AppHint("large", (), frozenset(), (first, second))
    rendered = render_hints([hint])
    assert len(rendered) <= 1200
    assert rendered.endswith("- " + first)
    assert second not in rendered
    assert render_hints([]) == ""


def _prompt_planner(enabled):
    planner = object.__new__(Planner)
    planner.app_hints = enabled
    planner.last_hint_ids = []
    planner.retrieval_block = lambda goal, observation: "# examples\n"
    return planner


def test_app_hint_prompt_is_byte_identical_when_off_or_unmatched():
    observation = 'app: Spotify | window: "Spotify"'
    goal = "play jazz on spotify"
    plain = _prompt_planner(False)
    enabled = _prompt_planner(True)
    expected = "# examples\n" + plain.user_message(goal, observation, None)
    assert plain.user_content(goal, observation, None) == expected
    assert enabled.user_content(
        "do something unusual", "app: Unknown | window: Home", None
    ) == "# examples\n" + enabled.user_message(
        "do something unusual", "app: Unknown | window: Home", None)
    hinted = enabled.user_content(goal, observation, None)
    rendered = render_hints(match_hints(goal, "Spotify"))
    assert hinted == "# examples\n" + rendered + "\n" + expected[len("# examples\n"):]
    assert enabled.last_hint_ids == ["spotify", "search_then_act"]


def test_app_hint_cli_and_offline_flags(monkeypatch):
    default, _ = cli.build_parser(["serve"])
    enabled, _ = cli.build_parser([
        "serve", "--planner-app-hints", "on", "--open-ended-route", "on"])
    assert cli.planner_opts(default)["app_hints"] is False
    assert cli.planner_opts(enabled)["app_hints"] is True
    assert enabled.open_ended_route == "on"

    offline = planner_offline.build_parser().parse_args(["--app-hints"])
    assert offline.app_hints is True
    summary = planner_offline.summarize(
        "app-hints", "fake", {"app_hints": True}, [{
            "tags": [], "pass": True, "strict_pass": True,
            "valid": True, "strict_valid": True, "skipped": 0,
            "ttft_ms": 1, "plan_ms": 1, "decode_tok_s": 1, "tokens": 1,
        }])
    assert summary["knobs"]["app_hints"] is True
    seen = {}

    class FakePlanner:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)
            self.tokenizer = type("Tokenizer", (), {
                "eos_token_id": 0,
                "encode": lambda self, text, add_special_tokens=False: [],
            })()

    monkeypatch.setattr("brain.planner.Planner", FakePlanner)
    planner_offline.Runner("fake", None, app_hints=True)
    assert seen["app_hints"] is True


def test_load_hints_returns_fresh_lists_from_cached_default():
    first = load_hints()
    first.clear()
    assert load_hints()


@pytest.mark.parametrize(("goal", "app", "route_hint", "expected"), [
    ("set a timer for 10 minutes", "", "", "clock"),
    ("pause the timer", "Clock", "the timer is in the Clock app's Timers tab", "clock"),
    ("pause it", "Clock", "", "clock"),
    ("remind me to call mom at 5", "", "", "reminders"),
    ("add milk", "", "use the Reminders app; reminder milk", "reminders"),
    ("make a note about the trip", "", "", "notes"),
    ("write down groceries", "", "use the Notes app; new note; text: eggs", "notes"),
    ("add an event lunch tomorrow at 3pm", "", "", "calendar"),
    ("text mom I'm running late", "", "", "messages"),
    ("tell Caleb hi", "", "use the Messages app; recipient Caleb", "messages"),
    ("reply to this email saying thanks", "", "", "mail"),
    ("say thanks", "Google Chrome",
     "the email is open in the browser/Mail; write a draft reply", "mail"),
    ("directions to SFO", "", "", "apple_maps"),
    ("add a marker here", "Adobe Premiere Pro", "", "premiere"),
    ("cut the clip", "", "use Adobe Premiere Pro; op cut", "premiere"),
])
def test_app_knowhow_entries_selected(goal, app, route_hint, expected):
    picked = [h.id for h in match_hints(goal, app, route_hint=route_hint)]
    assert picked[0] == expected


def test_app_knowhow_route_hint_beats_goal_words_and_app_is_word_matched():
    # agentic hint names the app; goal words naming another app come second
    picked = [h.id for h in match_hints(
        "text about the meeting", "",
        route_hint="use the Notes app; new note")]
    assert picked[0] == "notes"
    assert "messages" not in [h.id for h in match_hints("edit this", "TextEdit")]


def test_app_knowhow_tips_are_short_and_never_pixel_click_user_data():
    rows = {hint.id: hint for hint in load_hints()}
    for hid in ("clock", "reminders", "notes", "calendar", "messages",
                "mail", "apple_maps", "premiere"):
        assert 2 <= len(rows[hid].tips) <= 5, hid
        assert len(render_hints([rows[hid]])) <= 1200
    for hid in ("spotify", "mail", "messages", "notes", "calendar",
                "reminders", "finder_files", "rename_files", "system_settings"):
        for tip in rows[hid].tips:
            assert not re.search(r'\bclick\s+(["\d#<]|the\b|on\b)', tip), (hid, tip)
    assert any("ONCE" in tip for tip in rows["clock"].tips)
    assert all("confirm" in " ".join(rows[h].tips) for h in ("messages", "mail"))


def test_app_knowhow_entries_do_not_redirect_or_name_cross_app_targets():
    from brain.orchestrator import Orchestrator
    assert getattr(open_ended_redirect("find_file", "find the text file", None), "id", None) \
        != "messages"
    assert open_ended_redirect(
        "start_timer", "set a timer for 5 minutes", "safe") is None
    assert Orchestrator._goal_named_target("reply to this email") is None
    assert Orchestrator._goal_named_target("add a marker in premiere") is None
    assert Orchestrator._goal_named_target("pause the timer") == "clock"


def test_planner_prompt_uses_route_hint_for_app_tips():
    planner = _prompt_planner(True)
    content = planner.user_content(
        "pause it", "app: Clock | window: \"Clock\"", None,
        hint="the timer is in the Clock app's Timers tab")
    assert planner.last_hint_ids[0] == "clock"
    assert "press that button ONCE" in content
