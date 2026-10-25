import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
from brain import cli
from brain.catalog import Catalog
from brain.app_hints import (
    AppHint,
    load_hints,
    match_hints,
    open_ended_redirect,
    render_hints,
)
from brain.orchestrator import Orchestrator
from brain.planner import Planner
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


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


@pytest.mark.parametrize("enabled,expected", [
    (True, "planner"),
    (False, "answer"),
])
def test_open_ended_route_redirects_answer_when_enabled(
        tmp_path, enabled, expected):
    text = "add usb-c cable to my amazon cart"
    orch = Orchestrator(FakeServer(), Catalog.load(),
                        Tracer(tmp_path / "traces"), engine=FakeEngine())
    orch.open_ended_route = enabled
    trace = {"decisions": []}
    pre = SimpleNamespace(
        probs={"ANSWER": 0.95}, p_top=0.95, ms={}, top="ANSWER")

    async def planner_loop(goal, current_trace, hint=None):
        assert goal == text
        return "planner"

    async def answer(goal, current_trace):
        return "answer"

    orch._planner_loop = planner_loop
    orch._answer = answer
    assert asyncio.run(orch._engine_route(text, trace, pre=pre)) == expected
    if enabled:
        assert trace["open_ended"] == {"from": "ANSWER", "hint": "amazon"}
    else:
        assert "open_ended" not in trace


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
