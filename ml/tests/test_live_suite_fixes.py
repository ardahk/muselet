"""Regression coverage for routed live-suite argument and follow-up fixes."""

import asyncio
import json
import os
import time

import pytest

from brain import argfix, pathfind
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator, abs_level
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def run(coro):
    return asyncio.run(coro)


def _skill_rpcs(server):
    return [(params["name"], params["args"])
            for method, params in server.rpcs if method == "skill"]


def _traces(tracer):
    return [json.loads(line) for path in tracer.dir.glob("*.jsonl")
            for line in path.read_text().splitlines()]


class ResultServer(FakeServer):
    def __init__(self, responses=None):
        super().__init__()
        self.responses = responses or {}

    async def rpc(self, method, params, timeout=30):
        if method == "skill":
            self.rpcs.append((method, params))
            response = self.responses.get(params["name"])
            if callable(response):
                return response(params)
            return response or {"ok": True, "result": {}, "ms": 1}
        return await super().rpc(method, params, timeout)


def _orch(tmp_path, routes, args=None, server=None):
    engine = FakeEngine(routes, args or {})
    o = Orchestrator(server or FakeServer(), Catalog.load(),
                     Tracer(tmp_path / "traces"), engine=engine)
    return o, engine


@pytest.mark.parametrize("text,want", [
    ("silence", True), ("hush", True), ("quiet the sound", True),
    ("mute", True), ("sound off", True), ("audio is off", True),
    ("volume turned off", True), ("speakers are off", True),
    ("kill the sound", True), ("cut the sound", True),
    ("shut off the sound", True), ("turn off the sound", True),
    ("unmute", False), ("sound back on", False), ("sound on", False),
    ("audio is on", False), ("turn the sound back on", False),
    ("silence, the speakers!", True),
])
def test_mute_polarity_lexicon(text, want):
    assert argfix.polarity("mute", text) is want


@pytest.mark.parametrize("text,want", [
    ("dark mode", True), ("dark theme", True), ("night mode", True),
    ("go dark", True), ("light mode", False), ("light theme", False),
    ("turn off dark", False), ("turn off the dark", False),
    ("disable dark", False), ("disable the dark", False),
    ("dark mode off", False), ("dark theme off", False),
    ("go light", False),
])
def test_dark_mode_polarity_lexicon(text, want):
    assert argfix.polarity("dark_mode", text) is want


@pytest.mark.parametrize("skill", ["wifi", "bluetooth"])
@pytest.mark.parametrize("text,want", [
    ("wifi on", True), ("enable wifi", True), ("turn on wifi", True),
    ("connect wifi", True), ("wifi back on", True),
    ("turn wifi off and then on", True), ("wifi off", False),
    ("disable wifi", False), ("turn off wifi", False),
    ("disconnect wifi", False),
])
def test_network_polarity_lexicon(skill, text, want):
    assert argfix.polarity(skill, text) is want


def test_network_on_avoids_following_object_pronoun_and_detects_conflict():
    assert argfix.polarity("wifi", "turn off wifi on my mac") is False
    assert argfix.polarity("wifi", "wifi on and off") is None
    assert argfix.polarity("wifi", "turn it off and on again") is True


@pytest.mark.parametrize("text,skill,want", [
    ("go back to light mode", "dark_mode", False),
    ("turn off dark mode", "dark_mode", False),
    ("turn dark mode off", "dark_mode", False),
    ("turn off wifi on my mac", "wifi", False),
    ("turn it off and on again", "wifi", True),
])
def test_polarity_phrase_controls_routed_skill(tmp_path, text, skill, want):
    o, _ = _orch(tmp_path, {text: (skill, 0.95)},
                 {(skill, text): {}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [(skill, {"on": want})]


@pytest.mark.parametrize("skill,text", [
    ("mute", "don't mute"),
    ("wifi", "do not turn off wifi"),
    ("dark_mode", "don't enable dark mode"),
])
def test_negated_polarity_requests_slot_then_uses_answer(tmp_path, skill, text):
    o, _ = _orch(tmp_path, {text: (skill, 0.95), "off": ("ANSWER", 0.9)},
                 {(skill, text): {"on": True}})
    assert run(o.handle_utterance(text))["outcome"] == "awaiting_user"
    assert not _skill_rpcs(o.server)
    assert o._slot and o._slot["missing"] == ["on"]
    assert o.server.said[-1] == "On or off?"
    tr = _traces(o.tracer)[-1]
    assert {"polarity": "negated"} in tr["decisions"]

    run(o.handle_utterance("off"))
    assert _skill_rpcs(o.server) == [(skill, {"on": False})]
    assert o._slot is None


def test_polarity_overrides_conflicting_model_args(tmp_path):
    o, _ = _orch(tmp_path, {"silence the speakers": ("mute", 0.95)},
                 {("mute", "silence the speakers"): {"on": False}})
    run(o.handle_utterance("silence the speakers"))
    assert _skill_rpcs(o.server) == [("mute", {"on": True})]


def test_bare_not_does_not_negate_unmute_command(tmp_path):
    text = "the sound's not working, unmute it"
    o, _ = _orch(tmp_path, {text: ("mute", 0.95)},
                 {("mute", text): {"on": True}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [("mute", {"on": False})]
    assert o._slot is None


@pytest.mark.parametrize("text,skill,args,want_name,want_args", [
    ("turn it down a little", "change_volume", {}, "change_volume",
     {"delta": -10}),
    ("make it way louder", "change_volume", {}, "change_volume",
     {"delta": 30}),
    ("louder", "change_volume", {}, "change_volume", {"delta": 10}),
    ("turn it up a lot", "change_volume", {}, "change_volume",
     {"delta": 30}),
    ("make the screen dimmer", "set_brightness", {}, "set_brightness",
     {"delta": -10}),
    ("a lot brighter", "set_brightness", {}, "set_brightness",
     {"delta": 30}),
    ("all the way up", "change_volume", {}, "set_volume", {"level": 100}),
    ("brightness max", "set_brightness", {}, "set_brightness",
     {"level": 100}),
    ("volume to 30", "set_volume", {}, "set_volume", {"level": 30}),
])
def test_vague_delta_and_absolute_level(tmp_path, text, skill, args,
                                        want_name, want_args):
    o, _ = _orch(tmp_path, {text: (skill, 0.95)}, {(skill, text): args})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [(want_name, want_args)]


def test_model_delta_is_not_overridden(tmp_path):
    text = "make it way louder"
    o, _ = _orch(tmp_path, {text: ("change_volume", 0.95)},
                 {("change_volume", text): {"delta": -5}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [("change_volume", {"delta": -5})]


def test_abs_level_relative_guard_and_words():
    assert abs_level("turn it up by 20") is None
    assert abs_level("all the way up") == 100
    assert abs_level("all the way down") == 0
    assert abs_level("max") == 100
    assert abs_level("maximum") == 100
    assert abs_level("full") == 100
    assert abs_level("min") == 0
    assert abs_level("minimum") == 0


@pytest.mark.parametrize("text,view", [
    ("open my downloads as a list", "list"),
    ("open downloads list view", "list"),
    ("open downloads as icons", "icons"),
    ("open downloads icon view", "icons"),
    ("open downloads columns", "columns"),
    ("open downloads column view", "columns"),
    ("open downloads gallery", "gallery"),
])
def test_open_folder_extracts_finder_view(tmp_path, text, view):
    o, _ = _orch(tmp_path, {text: ("open_folder", 0.95)},
                 {("open_folder", text): {"path": "downloads"}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [
        ("open_folder", {"path": "downloads", "view": view})]


def test_open_folder_retries_without_view_and_sends_key_combo(tmp_path):
    def response(params):
        if "view" in params["args"]:
            return {"ok": False, "error":
                    "invalid params: open_folder: view must be "
                    "list|icons|columns|gallery"}
        return {"ok": True, "result": {}}

    text = "open my downloads as a list"
    server = ResultServer({"open_folder": response})
    o, _ = _orch(
        tmp_path, {text: ("open_folder", 0.95)},
        {("open_folder", text): {"path": "downloads"}}, server)
    run(o.handle_utterance(text))
    assert _skill_rpcs(server) == [
        ("open_folder", {"path": "downloads", "view": "list"}),
        ("open_folder", {"path": "downloads"})]
    assert ("act", {"op": "keys", "combo": "cmd+2"}) in server.rpcs
    assert any({"view_fallback": "list"} in trace["decisions"]
               for trace in _traces(o.tracer))


@pytest.mark.parametrize("name,text,args", [
    ("open_app", "open finder", {"app": "Finder"}),
    ("open_folder", "open my downloads", {"path": "downloads"}),
])
def test_not_frontmost_skill_fails_honestly(tmp_path, name, text, args):
    result = {"path": "/Users/test/Downloads"}
    server = ResultServer({
        name: {"ok": False, "error": "not_frontmost", "result": result}})
    o, _ = _orch(tmp_path, {text: (name, 0.95)},
                 {(name, text): args}, server)

    outcome = run(o.handle_utterance(text))

    assert outcome["outcome"] == "failed"
    assert server.said[-1] == "Opened it, but it didn't come to the front"
    assert server.uis[-1] == "confused"
    assert "success" not in server.uis
    assert o._ctx["last_action"] == "none"
    trace = _traces(o.tracer)[-1]
    assert {"not_frontmost": {"skill": name, "result": result}} \
        in trace["decisions"]
    assert any(rpc["result"].get("error") == "not_frontmost" and
               rpc["result"].get("result") == result for rpc in trace["rpc"])


def test_open_folder_not_frontmost_does_not_send_view_fallback_keys(tmp_path):
    text = "open my downloads as a list"
    server = ResultServer({
        "open_folder": {"ok": False, "error": "not_frontmost",
                        "result": {"path": "/Users/test/Downloads"}}})
    o, _ = _orch(tmp_path, {text: ("open_folder", 0.95)},
                 {("open_folder", text): {"path": "downloads"}}, server)

    outcome = run(o.handle_utterance(text))

    assert outcome["outcome"] == "failed"
    assert server.said[-1] == "Opened it, but it didn't come to the front"
    assert _skill_rpcs(server) == [
        ("open_folder", {"path": "downloads", "view": "list"})]
    assert not any(method == "act" and params.get("op") == "keys"
                   for method, params in server.rpcs)


def test_open_folder_without_view_words_has_no_view_arg(tmp_path):
    text = "open my downloads"
    o, _ = _orch(tmp_path, {text: ("open_folder", 0.95)},
                 {("open_folder", text): {"path": "downloads"}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [("open_folder", {"path": "downloads"})]


def test_path_aliases_and_object_phrases():
    for phrase, want in [
            ("desktop", "~/Desktop"), ("my desktop", "~/Desktop"),
            ("documents", "~/Documents"), ("my downloads", "~/Downloads"),
            ("home", "~"), ("applications", "/Applications"),
            ("pictures", "~/Pictures"), ("music", "~/Music"),
            ("movies", "~/Movies"), ("trash", "~/.Trash")]:
        assert pathfind.alias(phrase) == want
        assert pathfind.is_alias(phrase)
    assert pathfind.object_phrase(
        "move_to_trash", "move the old draft to the trash") == "old draft"
    assert pathfind.object_phrase(
        "open_file", "open the file called invoice") == "invoice"
    assert pathfind.object_phrase(
        "open_folder", "open trip photos folder in Finder") == "trip photos"


def test_vague_delta_degrees_and_duration_helper():
    for text in ("a little louder", "a bit louder", "slightly louder",
                 "a touch louder", "a notch louder"):
        assert argfix.vague_delta(text) == 10
    for text in ("a lot louder", "way louder", "much louder",
                 "really louder", "a ton louder"):
        assert argfix.vague_delta(text) == 30
    assert argfix.vague_delta("up and down") is None
    assert argfix.recover_duration("five", "timer for five minutes") == 300
    assert argfix.recover_duration("5", "timer for 5") == "ask"


def test_resolve_normalizes_case_dash_underscore_and_extension(tmp_path):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    expected = desktop / "Muselet_Trash-Probe.TXT"
    expected.write_text("x")
    assert pathfind.resolve("muselet trash probe", home=str(home)) == [
        str(expected)]


def test_move_to_trash_resolves_utterance_phrase_and_confirms_full_path(
        tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    (home / "Documents").mkdir()
    (home / "Downloads").mkdir()
    expected = home / "Desktop" / "muselet trash probe.txt"
    expected.write_text("x")
    (home / "Documents" / "muselet invoices.pdf").write_text("x")
    monkeypatch.setenv("HOME", str(home))
    text = "move muselet trash probe to the trash"
    o, _ = _orch(tmp_path, {text: ("move_to_trash", 0.95)},
                 {("move_to_trash", text): {"path": "muselet invoices"}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [
        ("move_to_trash", {"path": str(expected), "confirmed": True})]
    assert o.server.confirms == [
        "Move ~/Desktop/muselet trash probe.txt to Trash?"]


def test_path_ambiguity_and_missing_path_ask_without_rpc(tmp_path, monkeypatch):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    documents = home / "Documents"
    desktop.mkdir(parents=True)
    documents.mkdir()
    (desktop / "project notes.txt").write_text("x")
    (documents / "project notes.md").write_text("x")
    monkeypatch.setenv("HOME", str(home))
    text = "open project notes"
    o, _ = _orch(tmp_path, {text: ("open_file", 0.95)},
                 {("open_file", text): {"path": "project notes"}})
    assert run(o.handle_utterance(text))["outcome"] == "awaiting_user"
    assert not _skill_rpcs(o.server)
    assert o._slot and o._slot["missing"] == ["path"]
    assert o.server.said[-1].startswith("Which one:")
    assert len(o.server.said[-1].split()) <= 12

    other = "open unknown document"
    o2, _ = _orch(tmp_path / "other", {other: ("open_file", 0.95)},
                  {("open_file", other): {"path": "unknown document"}})
    assert run(o2.handle_utterance(other))["outcome"] == "awaiting_user"
    assert not _skill_rpcs(o2.server)
    assert o2.server.said[-1] == \
        "I couldn't find unknown document. Which file?"


def test_existing_path_and_folder_alias_are_not_resolved(tmp_path):
    existing = tmp_path / "report.pdf"
    existing.write_text("x")
    text = "open report"
    o, _ = _orch(tmp_path, {text: ("open_file", 0.95)},
                 {("open_file", text): {"path": str(existing)}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [("open_file", {"path": str(existing)})]

    folder = "open my downloads"
    o2, _ = _orch(tmp_path / "alias", {folder: ("open_folder", 0.95)},
                  {("open_folder", folder): {"path": "downloads"}})
    run(o2.handle_utterance(folder))
    assert _skill_rpcs(o2.server) == [
        ("open_folder", {"path": "downloads"})]


def test_path_phrase_resolves_when_model_omits_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    expected = desktop / "invoice.pdf"
    expected.write_text("x")
    monkeypatch.setenv("HOME", str(home))
    text = "open the file called invoice"
    o, _ = _orch(tmp_path, {text: ("open_file", 0.95)},
                 {("open_file", text): {}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [
        ("open_file", {"path": str(expected)})]


def test_resolve_does_not_search_beyond_one_subdirectory(tmp_path):
    home = tmp_path / "home"
    deep = home / "Desktop" / "one" / "two"
    deep.mkdir(parents=True)
    (deep / "deep target.txt").write_text("x")
    assert pathfind.resolve("deep target", home=str(home)) == []


def test_resolve_does_not_follow_symlinks(tmp_path):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    outside = tmp_path / "outside"
    desktop.mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.txt").write_text("x")
    (desktop / "linked").symlink_to(outside, target_is_directory=True)
    assert pathfind.resolve("secret", home=str(home)) == []


def test_resolve_entry_and_time_budget_caps_large_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    for i in range(2500):
        (desktop / f"entry-{i:04}.txt").touch()

    count = [0]
    real_scandir = os.scandir

    class CountedScandir:
        def __init__(self, path):
            self.entries = real_scandir(path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.entries.close()

        def __iter__(self):
            for entry in self.entries:
                count[0] += 1
                yield entry

    monkeypatch.setattr(pathfind.os, "scandir", CountedScandir)
    started = time.perf_counter()
    assert pathfind.resolve("absent", home=str(home)) == []
    elapsed = time.perf_counter() - started
    assert count[0] <= 2000
    assert elapsed < 0.5


def test_compound_new_folder_then_open_uses_alias_path(tmp_path):
    text = "create a folder on my desktop called trip photos and open it"
    first = "create a folder on my desktop called trip photos"
    o, _ = _orch(
        tmp_path, {first: ("new_folder", 0.95)},
        {("new_folder", first): {"parent": "my desktop",
                                 "name": "trip photos"}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [
        ("new_folder", {"parent": "my desktop", "name": "trip photos"}),
        ("open_folder", {"path": "~/Desktop/trip photos"})]
    assert any("compound_followup" in decision
               for trace in _traces(o.tracer)
               for decision in trace["decisions"])


def test_compound_new_folder_prefers_result_path(tmp_path):
    text = "create a folder on my desktop called trip photos and open it"
    first = "create a folder on my desktop called trip photos"
    result_path = str(tmp_path / "actual" / "trip photos")
    server = ResultServer({
        "new_folder": {"ok": True, "result": {"path": result_path}},
    })
    o, _ = _orch(
        tmp_path, {first: ("new_folder", 0.95)},
        {("new_folder", first): {"parent": "my desktop",
                                 "name": "trip photos"}}, server)
    run(o.handle_utterance(text))
    assert _skill_rpcs(server)[-1] == (
        "open_folder", {"path": result_path})


def test_compound_new_folder_followup_not_frontmost_fails_honestly(tmp_path):
    text = "create a folder on my desktop called trip photos and open it"
    first = "create a folder on my desktop called trip photos"
    result_path = str(tmp_path / "actual" / "trip photos")
    server = ResultServer({
        "new_folder": {"ok": True, "result": {"path": result_path}},
        "open_folder": {"ok": False, "error": "not_frontmost",
                        "result": {"path": result_path}},
    })
    o, _ = _orch(
        tmp_path, {first: ("new_folder", 0.95)},
        {("new_folder", first): {"parent": "my desktop",
                                 "name": "trip photos"}}, server)

    outcome = run(o.handle_utterance(text))

    assert outcome["outcome"] == "failed"
    assert server.said[-1] == "Opened it, but it didn't come to the front"
    assert server.uis[-1] == "confused"


def test_compound_screenshot_then_open_uses_result_path(tmp_path):
    text = "take a screenshot and open it"
    screenshot_path = str(tmp_path / "capture.png")
    server = ResultServer({
        "take_screenshot": {"ok": True, "result": {"path": screenshot_path}},
    })
    o, _ = _orch(tmp_path, {"take a screenshot": ("take_screenshot", 0.95)},
                 {("take_screenshot", "take a screenshot"): {}}, server)
    run(o.handle_utterance(text))
    assert _skill_rpcs(server) == [
        ("take_screenshot", {}),
        ("open_file", {"path": screenshot_path})]


def test_compound_screenshot_followup_not_frontmost_fails_honestly(tmp_path):
    text = "take a screenshot and open it"
    screenshot_path = str(tmp_path / "capture.png")
    server = ResultServer({
        "take_screenshot": {"ok": True, "result": {"path": screenshot_path}},
        "open_file": {"ok": False, "error": "not_frontmost",
                      "result": {"path": screenshot_path}},
    })
    o, _ = _orch(tmp_path, {"take a screenshot": ("take_screenshot", 0.95)},
                 {("take_screenshot", "take a screenshot"): {}}, server)

    outcome = run(o.handle_utterance(text))

    assert outcome["outcome"] == "failed"
    assert server.said[-1] == "Opened it, but it didn't come to the front"
    assert server.uis[-1] == "confused"


def test_compound_screenshot_without_result_path_fails_friendly(tmp_path):
    text = "take a screenshot and open it"
    server = ResultServer()
    o, _ = _orch(tmp_path, {"take a screenshot": ("take_screenshot", 0.95)},
                 {("take_screenshot", "take a screenshot"): {}}, server)
    assert run(o.handle_utterance(text))["outcome"] == "failed"
    assert "screenshot" in o.server.said[-1].lower()
    assert [name for name, _ in _skill_rpcs(server)] == ["take_screenshot"]


def test_compound_note_show_does_not_add_action(tmp_path):
    text = "make a note about groceries and show it"
    first = "make a note about groceries"
    o, _ = _orch(
        tmp_path, {first: ("new_note", 0.95)},
        {("new_note", first): {"title": "Groceries", "body": "Groceries"}})
    run(o.handle_utterance(text))
    assert [name for name, _ in _skill_rpcs(o.server)] == ["new_note"]


def test_open_it_after_noncreating_skill_routes_normally(tmp_path):
    existing = tmp_path / "item.txt"
    existing.write_text("x")
    text = "mute and open it"
    o, engine = _orch(
        tmp_path, {"mute": ("mute", 0.95), "open it": ("open_file", 0.95)},
        {("mute", "mute"): {"on": True},
         ("open_file", "open it"): {"path": str(existing)}})
    run(o.handle_utterance(text))
    assert [name for name, _ in _skill_rpcs(o.server)] == ["mute", "open_file"]
    assert "open it" in engine.route_calls


def test_rejected_compound_routes_whole_utterance_to_planner_with_hint(
        tmp_path, monkeypatch):
    text = "mute and open notes"
    o, _ = _orch(
        tmp_path, {"mute": ("mute", 0.95), "open notes": ("open_app", 0.6),
                   text: ("open_app", 0.95)},
        {("mute", "mute"): {"on": True}})
    calls = []

    async def planner(goal, trace, hint=None, answer=None):
        calls.append((goal, hint))
        return "planner"

    monkeypatch.setattr(o, "_planner_loop", planner)
    run(o.handle_utterance(text))
    assert calls == [(text, "open_app")]
    assert not _skill_rpcs(o.server)
    assert _traces(o.tracer)[-1]["compound_to_planner"] == {
        "hint": "open_app", "clauses": ["mute", "open notes"]}


@pytest.mark.parametrize("text,raw,want", [
    ("set a timer for five seconds", "5", 5),
    ("set a timer for 5 minutes", "5", 300),
    ("an hour and a half", "1", 5400),
    ("90 seconds", "90", 90),
    ("half an hour", "30", 1800),
])
def test_duration_recovery_sends_integer_seconds(tmp_path, text, raw, want):
    o, _ = _orch(tmp_path, {text: ("start_timer", 0.95)},
                 {("start_timer", text): {"duration": raw}})
    run(o.handle_utterance(text))
    assert _skill_rpcs(o.server) == [
        ("start_timer", {"duration": want})]


def test_execute_actions_coerces_planner_duration_to_integer_seconds(tmp_path):
    o, _ = _orch(tmp_path, {})
    outcome = run(o.execute_actions([
        {"op": "skill", "name": "start_timer", "args": {"duration": "600"}}
    ]))
    assert outcome == "ok"
    assert _skill_rpcs(o.server) == [
        ("start_timer", {"duration": 600})]


def test_unitless_duration_asks_for_unit_then_fills(tmp_path):
    text = "a timer for 5"
    o, _ = _orch(tmp_path, {text: ("start_timer", 0.95),
                            "minutes": ("ANSWER", 0.9)},
                 {("start_timer", text): {"duration": "5"}})
    assert run(o.handle_utterance(text))["outcome"] == "awaiting_user"
    assert o.server.said[-1] == "Five seconds or five minutes?"
    assert o._slot["duration_number"] == "5"
    run(o.handle_utterance("minutes"))
    assert _skill_rpcs(o.server) == [
        ("start_timer", {"duration": 300})]


def test_datetime_argument_is_not_recovered_as_duration(tmp_path):
    text = "remind me to call mom at 5"
    o, _ = _orch(
        tmp_path, {text: ("create_reminder", 0.95)},
        {("create_reminder", text): {"title": "call mom", "due": "5"}})
    run(o.handle_utterance(text))
    assert not any("seconds or" in bubble for bubble in o.server.said)
    assert not (o._slot and "duration_number" in o._slot)
