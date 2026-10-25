import json
import statistics
import time

import brain.memory as memory_module
from brain.memory import WorkingMemory, detect, eval_adapter, resolve
from brain.memory.rewrite import STATIC, _valid, llm_rewrite
from brain.memory.rules import SEARCH_URLS
from brain.memory.working import site_for_url


class _Catalog:
    def __init__(self, risks=None):
        self.risks = risks or {}

    def risk(self, name):
        return self.risks.get(name, "safe")

    def get(self, name):
        required = {"type_text": "text", "set_volume": "level"}.get(name)
        return {"args": ([{"name": required, "required": True}]
                         if required else [])}


def _memory(skill="open_url", args=None, *, t=10, ok=True,
            resolved=None, ctx=None, result=None):
    wm = WorkingMemory()
    wm.record(
        "navigate to Wikipedia", resolved or skill, skill, args or {}, ok,
        ctx or {"app": "Zen"}, t=t, result=result)
    return wm


def test_wikipedia_site_search_is_scoped_and_direct():
    wm = _memory(args={"url": "https://en.wikipedia.org/wiki/Cat"})
    result = resolve("search for history", wm, {"app": "Zen"}, 11,
                     catalog=_Catalog())
    assert result.path == "rule"
    assert result.changed
    assert "wikipedia" in result.text
    assert "history" in result.text
    assert "google" not in result.text
    assert result.direct == {
        "skill": "open_url",
        "args": {"url": "https://en.wikipedia.org/w/index.php?search=history"},
    }


def test_site_search_does_not_override_explicit_site_or_self_contained():
    wm = _memory(args={"url": "https://en.wikipedia.org/"})
    assert resolve("search google for flights", wm, {"app": "Zen"}, 11).text == \
        "search google for flights"
    assert resolve("open Safari", wm, {"app": "Zen"}, 11).text == "open Safari"


def test_site_search_requires_live_turn_and_browser_focus():
    wm = _memory(args={"url": "https://en.wikipedia.org/"}, t=0)
    assert resolve("search for history", wm, {"app": "Zen"}, 2000).changed is False

    recent = _memory(args={"url": "https://en.wikipedia.org/"}, t=10)
    assert "site" not in recent.focus(11, {"app": "Finder"})
    assert resolve("search for history", recent,
                   {"app": "Finder", "url": ""}, 11).changed is False


def test_search_without_history_and_safe_bare_search_continuation():
    fresh = WorkingMemory()
    result = resolve("look up renewable energy", fresh,
                     {"app": "Safari", "url": "https://news.ycombinator.com/"},
                     1)
    assert result.changed
    assert result.text.startswith("open https://hn.algolia.com/?q=")
    assert result.direct["skill"] == "open_url"

    history = _memory(
        args={"url": "https://docs.python.org/3/search.html?q=iterators"})
    result = resolve(
        "and generators", history,
        {"app": "Google Chrome",
         "url": "https://docs.python.org/3/search.html?q=iterators"},
        11)
    assert result.changed
    assert "generators" in result.text
    assert "google.com" not in result.text
    assert resolve(
        "open Finder", history,
        {"app": "Google Chrome",
         "url": "https://docs.python.org/3/search.html?q=iterators"},
        11).changed is False


def test_other_followups_do_not_capture_native_commands():
    wm = _memory("send_message", {"to": "Arda", "body": "secret"})
    assert resolve("turn the volume up", wm, {}, 11).changed is False
    assert resolve("text Caleb hello", wm, {}, 11).changed is False


def test_focus_ttl_app_switch_url_override_and_host_rules():
    wm = _memory(args={"url": "https://www.en.wikipedia.org/wiki/Cat"})
    assert wm.focus(11, {"app": "Zen"})["site"] == "wikipedia.org"
    assert wm.focus(11, {"app": "Zen", "url": "https://maps.google.com/"})[
        "site"] == "maps.google.com"
    assert "site" not in wm.focus(11, {"app": "Finder"})
    assert site_for_url("https://mail.google.com/") == "mail.google.com"
    assert site_for_url("https://www.google.com/maps/search/") == \
        "maps.google.com"
    assert wm.focus(611, {"app": "Zen"}) == {}


def test_recording_nonbrowser_app_switch_clears_stale_url():
    wm = _memory(args={"url": "https://en.wikipedia.org/"})
    wm.record("open Finder", "open Finder", "open_app", {"app": "Finder"},
              True, {"app": "Finder", "url": "https://en.wikipedia.org/"},
              t=11)
    focus = wm.focus(12, {"app": "Zen"})
    assert focus == {"app": "Finder"}


def test_again_and_undo_rules():
    wm = _memory("set_volume", {"level": 30}, resolved="set volume to 30")
    again = resolve("do that again", wm, {}, 11, catalog=_Catalog())
    assert again.path == "rule"
    assert "30" in again.text
    assert again.direct == {
        "skill": "set_volume", "args": {"level": 30}}

    dark = _memory("dark_mode", {"on": True})
    assert "dark mode" in resolve("undo", dark, {}, 11).text
    assert "off" in resolve("undo", dark, {}, 11).text

    volume = _memory("set_volume", {"level": 70}, result={"previous": 50})
    assert "50" in resolve("undo", volume, {}, 11).text

    layout = _memory("window_layout", {"layout": "left"})
    ask = resolve("undo", layout, {}, 11)
    assert ask.path == "ask"
    assert ask.ask == "I can't undo that. What should I do?"


def test_again_renders_actions_and_failed_turns_ask():
    shot = _memory("take_screenshot", {"region": "window"})
    assert resolve("once more", shot, {}, 11).text == \
        "take a screenshot of the window"
    failed = _memory("set_volume", {"level": 30}, ok=False)
    assert resolve("repeat", failed, {}, 11).ask == "What should I do again?"


def test_person_and_item_substitution_never_invent_referents():
    person = _memory("send_message",
                     {"to": "Mom", "body": "I'm late"},
                     resolved="send message to Mom")
    result = resolve("send her a message saying hi", person, {}, 11)
    assert result.changed
    assert "Mom" in result.text
    assert person.last(11).args == {"to": "Mom", "body": "I'm late"}

    unknown = _memory("open_url", {"url": "https://example.com"})
    unresolved = resolve("send him a message", unknown, {}, 11)
    assert not unresolved.changed
    assert "him" in unresolved.text

    typed = _memory("type_text", {"text": "private content"},
                    resolved="type_text private content")
    assert resolve("again", typed, {}, 11,
                   catalog=_Catalog()).direct is None

    file = _memory("open_file", {"path": "report.pdf"})
    move = resolve("move it to the trash", file, {}, 11)
    assert move.changed
    assert "report.pdf" in move.text


def test_refinement_and_correction():
    volume = _memory("change_volume", {"delta": 10})
    refined = resolve("a bit more", volume, {}, 11)
    assert refined.changed
    assert refined.direct == {
        "skill": "change_volume", "args": {"delta": 10}}

    correction = _memory("open_app", {"app": "Notes"}, resolved="open Notes")
    fixed = resolve("no, I meant Safari", correction, {}, 11)
    assert fixed.changed
    assert fixed.text == "open Safari"
    assert resolve("I meant Safari", correction, {}, 11).text == "open Safari"


def test_eval_adapter_replays_resolved_history_for_chained_value_changes():
    history = [
        {
            "utterance": "add a design review at 9 am monday",
            "ctx": {"app": "Calendar", "t": 1},
            "outcome": {
                "skill": "create_event",
                "args": {"title": "Design review", "start": "monday 09:00"},
                "ok": True,
            },
        },
        {
            "utterance": "make it wednesday instead",
            "ctx": {"app": "Calendar", "t": 2},
            "outcome": {"skill": "planner", "args": {}, "ok": True},
        },
    ]
    result = eval_adapter(
        "and ten thirty not 9", {"app": "Calendar", "t": 3}, history)
    assert result["path"] == "rule"
    assert "design review" in result["text"]
    assert "wednesday" in result["text"]
    assert "10:30 am" in result["text"]


def test_search_refinements_reuse_prior_query_and_kind():
    search = _memory("web_search", {"query": "farmers markets near me"},
                     resolved="search for farmers markets near me")
    result = resolve("just for this weekend", search, {}, 11)
    assert result.text == \
        "search for farmers markets near me this weekend"

    music = _memory("play_music", {"query": "acoustic study mix"},
                    resolved="play acoustic study mix")
    assert resolve("something more energetic", music, {}, 11).text == \
        "play energetic acoustic study mix"


def test_search_refinement_requires_search_history():
    note = _memory("new_note", {"title": "Packing"})
    for utterance in ("just do it", "only if it rains",
                      "something more colorful"):
        result = resolve(utterance, note, {}, 11)
        assert not result.changed


def test_same_query_substitution_is_conservative():
    search = _memory(
        "web_search", {"query": "top documentaries for travel"},
        resolved="search for top documentaries for travel")
    result = resolve("same but for audiobooks", search, {}, 11)
    assert result.text == "search for top audiobooks for travel"

    ambiguous = _memory(
        "web_search", {"query": "books reviews for students"},
        resolved="search for books reviews for students")
    assert not resolve("same thing but for podcasts",
                       ambiguous, {}, 11).changed


def test_event_reminder_and_timer_value_refinements():
    event = _memory(
        "create_event", {"title": "Dentist", "start": "monday 09:00"},
        resolved="add a dentist appointment at 9 am monday")
    assert resolve("make it thursday instead", event, {}, 11).text == \
        "add a dentist appointment at 9 am thursday"
    assert resolve("and seven fifteen not 9", event, {}, 11).text == \
        "add a dentist appointment at 7:15 am monday"

    timer = _memory(
        "start_timer", {"duration": "20m", "label": "reading"},
        resolved="start a twenty minute timer for reading")
    assert resolve("make it forty instead", timer, {}, 11).text == \
        "start a 40 minute timer for reading"


def test_value_corrections_use_args_and_accent_insensitive_matches():
    message = _memory(
        "send_message", {"to": "Júlia", "body": "Bring the adapter"},
        resolved="text Júlia saying Bring the adapter")
    result = resolve("no, Marco, not Julia", message, {}, 11)
    assert "Marco" in result.text
    assert "adapter" in result.text

    search = _memory(
        "web_search", {"query": "café dining"},
        resolved="search for café dining")
    assert resolve("no, tea, not cafe", search, {}, 11).text == \
        "search for tea dining"

    app = _memory("quit_app", {"app": "Illustrator"},
                  resolved="quit illustr")
    assert resolve("sorry, I meant Preview", app, {}, 11).text == \
        "quit Preview"


def test_other_option_uses_recent_two_item_list():
    wm = WorkingMemory()
    wm.record(
        "make a note: drinks, tea and coffee", "make a note: tea and coffee",
        "new_note", {"title": "Drinks", "body": "Tea and coffee"},
        True, {"app": "Notes"}, t=1)
    wm.record(
        "remind me to buy tea", "remind me to buy tea",
        "create_reminder", {"title": "Buy tea"}, True,
        {"app": "Reminders"}, t=2)
    assert resolve("no, the other one", wm, {}, 3).text == \
        "remind me to buy coffee"

    missing = _memory("find_file", {"query": "invoice", "kind": "pdf"})
    assert not resolve("the other one", missing, {}, 11).changed


def test_exact_the_x_one_correction_replaces_noun_modifier():
    export = _memory(
        "premiere_command", {"command": "export", "preset": "Mobile 720p"},
        resolved="export this with the mobile 720p preset")
    assert resolve("no, the cinema one", export, {}, 11).text == \
        "export this with the cinema 720p preset"


def test_undo_replays_earlier_same_skill_without_inverse():
    wm = WorkingMemory()
    wm.record("tile this window left", "tile this window left",
              "window_layout", {"layout": "left"}, True,
              {"app": "Pages"}, t=1)
    wm.record("make it full screen", "make the window full screen",
              "window_layout", {"layout": "full"}, True,
              {"app": "Pages"}, t=2)
    assert resolve("go back to how it was", wm, {}, 3).text == \
        "tile this window left"


def test_undo_does_not_replay_prior_delete():
    wm = WorkingMemory()
    wm.record("delete the file report.pdf", "delete the file report.pdf",
              "delete_file", {"path": "report.pdf"}, True,
              {"app": "Finder"}, t=1)
    wm.record("delete the file notes.txt", "delete the file notes.txt",
              "delete_file", {"path": "notes.txt"}, True,
              {"app": "Finder"}, t=2)
    result = resolve("undo", wm, {}, 3)
    assert result.path == "ask" or not result.changed
    assert "delete the file" not in result.text.casefold()


def test_undo_does_not_replay_irreversible_text_from_setter():
    wm = WorkingMemory()
    wm.record("send the schedule and put the window left",
              "send the schedule and put the window left",
              "window_layout", {"layout": "left"}, True,
              {"app": "Finder"}, t=1)
    wm.record("send the schedule and put the window right",
              "send the schedule and put the window right",
              "window_layout", {"layout": "right"}, True,
              {"app": "Finder"}, t=2)
    result = resolve("undo", wm, {}, 3)
    assert result.path == "ask" or not result.changed


def test_non_replay_reason_cannot_inherit_irreversible_guard(monkeypatch):
    wm = _memory(
        "send_message", {"to": "Dana", "body": "send the schedule"},
        resolved="text Dana saying send the schedule")
    monkeypatch.setattr(
        memory_module, "detect",
        lambda *_args, **_kwargs: "refinement")
    monkeypatch.setattr(
        memory_module, "apply",
        lambda text, reason, *_args, **_kwargs:
            memory_module.Resolution("rule", "send the schedule", True,
                                     reason))
    result = memory_module.resolve("make it louder", wm, {}, 11)
    assert result.path == "none"
    assert result.reason == "guard"
    assert not result.changed


def test_layout_refinement_rewrites_prior_direction_after_app_switch():
    layout = _memory(
        "window_layout", {"layout": "left"},
        resolved="snap this to the left half", ctx={"app": "Pages"})
    assert resolve("now this one on the right", layout,
                   {"app": "Safari"}, 11).text == \
        "snap this to the right half"


def test_created_items_and_stt_item_commands_resolve_referents():
    app = _memory("play_music", {"query": "piano"}, ctx={"app": "Music"})
    assert resolve("hyde it", app, {"app": "Music"}, 11).text == \
        "hide Music"

    file = _memory("open_file", {"path": "~/Desktop/Draft.pdf"})
    assert "Draft.pdf" in resolve("tras it", file, {}, 11).text

    note = _memory(
        "new_note", {"title": "Garden supplies"},
        resolved="make a note called Garden supplies")
    assert resolve("remind me about it tomorrow", note, {}, 11).text == \
        "remind me about Garden supplies tomorrow"
    assert resolve("add soil to it", note, {}, 11).text == \
        "add soil to the Garden supplies note"


def test_try_known_site_reuses_prior_query_but_unknown_target_does_not():
    search = _memory(
        "open_url",
        {"url": "https://www.google.com/search?q=camping+stoves"},
        resolved="open https://www.google.com/search?q=camping+stoves")
    result = resolve("now try ebay", search, {"app": "Safari"}, 11)
    assert "ebay.com" in result.text
    assert "camping" in result.text
    assert "stoves" in result.text
    assert not resolve("now try lakeside", search, {"app": "Safari"}, 11).changed
    assert not resolve("try amazon.com", search,
                       {"app": "Safari"}, 11).changed
    assert not resolve("try when did it open", search,
                       {"app": "Safari"}, 11).changed


def test_person_selection_uses_all_turns_and_gender_hints():
    wm = WorkingMemory()
    wm.record("text Noah about the reservation",
              "text Noah saying the reservation is confirmed",
              "send_message",
              {"to": "Noah", "body": "The reservation is confirmed"},
              True, {"app": "Messages"}, t=1)
    wm.record("make a reminder to call Priya",
              "make a reminder to call Priya", "create_reminder",
              {"title": "Call Priya"}, True, {"app": "Reminders"}, t=2)
    result = resolve("send him the updated time", wm, {}, 3)
    assert result.changed
    assert "Noah" in result.text

    ambiguous = WorkingMemory()
    ambiguous.record("plan lunch with Evan and Isaac",
                     "plan lunch with Evan and Isaac", "create_event",
                     {"title": "Lunch with Evan and Isaac"}, True,
                     {"app": "Calendar"}, t=1)
    result = resolve("message him about the location", ambiguous, {}, 2)
    assert not result.changed


def test_person_pronouns_use_recent_comms_recipient_not_body_names():
    wm = WorkingMemory()
    wm.record(
        "message Noah that yoga moved to Sunday",
        "message Noah saying yoga moved to Sunday", "send_message",
        {"to": "Noah", "body": "Yoga moved to Sunday"}, True,
        {"app": "Messages"}, t=1)
    wm.record(
        "remind me to call Grace", "remind me to call Grace",
        "create_reminder", {"title": "Call Grace"}, True,
        {"app": "Reminders"}, t=2)

    result = resolve("tex him the studio is on Elm Street", wm, {}, 3)
    assert result.changed
    assert result.text == "text Noah the studio is on Elm Street"


def test_person_pronouns_use_to_for_each_comms_skill_and_unknown_gender():
    for skill in ("send_message", "compose_email", "draft_email"):
        wm = WorkingMemory()
        wm.record("message Xinyi", "message Xinyi", skill,
                  {"to": "Xinyi", "body": "The report is ready"},
                  True, {"app": "Messages"}, t=1)
        wm.record("open the budget file", "open ~/Documents/Budget.xlsx",
                  "open_file", {"path": "~/Documents/Budget.xlsx"}, True,
                  {"app": "Finder"}, t=2)
        result = resolve("please email her the report", wm, {}, 3)
        assert result.changed
        assert "Xinyi" in result.text
        meeting = resolve("schedule a meeting with her", wm, {}, 3)
        assert meeting.changed
        assert "with Xinyi" in meeting.text


def test_person_pronoun_after_event_can_resolve_event_destination():
    wm = WorkingMemory()
    wm.record(
        "create an event physio with doctor Amara Okafor",
        "create event Physio with Dr. Amara Okafor", "create_event",
        {"title": "Physio with Dr. Amara Okafor"}, True,
        {"app": "Calendar"}, t=1)

    result = resolve("remind me to ask Leo to drive me there", wm, {}, 2)
    assert result.changed
    assert result.text == "remind me to ask Leo to drive me Physio"


def test_item_referent_uses_current_app_and_parent_folder():
    app = _memory("open_app", {"app": "Calendar"}, ctx={"app": "Calendar"})
    assert resolve("hide it", app, {"app": "Calendar"}, 11).text == \
        "hide Calendar"
    folder = _memory("new_folder", {
        "parent": "~/Documents/Trips", "name": "Receipts"})
    assert "~/Documents/Trips/Receipts" in resolve(
        "make another folder in there", folder, {}, 11).text


def test_utterance_normalization_preserves_unchanged_text():
    volume = _memory("set_volume", {"level": 35})
    original = "uh, show me several more options"
    result = resolve(original, volume, {}, 11)
    assert result.text == original
    assert not result.changed
    assert resolve("um, agin", volume, {}, 11).text == \
        "set the volume to 35"


def test_refinement_only_matches_short_commands():
    volume = _memory("set_volume", {"level": 40})
    utterance = "add milk to the list too"
    result = resolve(utterance, volume, {}, 11)
    assert result.text == utterance
    assert not result.changed
    assert detect(utterance, volume, {}, 11) is None

    change = _memory("change_volume", {"delta": 10})
    utterance = "show me more results"
    result = resolve(utterance, change, {}, 11)
    assert result.text == utterance
    assert not result.changed
    assert detect(utterance, change, {}, 11) is None

    assert detect("a bit more", change, {}, 11) == "refinement"
    assert resolve("a bit more", change, {}, 11).changed
    assert detect("louder", change, {}, 11) is None


def test_native_commands_and_nonreferential_pronouns_skip_llm():
    calls = []

    def forbidden_llm(*args):
        calls.append(args)
        raise AssertionError("native command reached the LLM")

    music = _memory("open_app", {"app": "Music"}, resolved="open Music")
    for utterance in ("what time is it", "turn it up"):
        assert detect(utterance, music, {}, 11) is None
        result = resolve(utterance, music, {}, 11, llm=forbidden_llm)
        assert result.text == utterance
        assert not result.changed

    file = _memory("open_file", {"path": "calendar.txt"})
    for utterance in (
            "what's on my calendar this week",
            "set a timer for one minute",
            "remind me that the meeting is at noon",
            "say that I want coffee",
            "saying that the report is ready",
            "tell Alex that the meeting moved"):
        assert detect(utterance, file, {}, 11) is None
        result = resolve(utterance, file, {}, 11, llm=forbidden_llm)
        assert result.text == utterance
        assert not result.changed

    assert calls == []


def test_deictic_this_is_not_a_pronoun_but_layout_referents_are():
    music = _memory("open_app", {"app": "Music"}, resolved="open Music")

    for utterance in ("screenshot this window", "skip this song"):
        assert detect(utterance, music, {}, 11) is None
        result = resolve(utterance, music, {}, 11)
        assert result.text == utterance
        assert not result.changed

    assert detect("snap this to the left half", music, {}, 11) == "item"
    assert detect("now this one on the right", music, {}, 11) == "pronoun"


def test_selection_idiom_stays_native_and_does_not_reach_llm():
    wm = _memory("open_file", {"path": "~/Documents/report.txt"})
    calls = []

    def forbidden_llm(*args):
        calls.append(args)
        raise AssertionError("native selection command reached the LLM")

    assert detect("copy that", wm, {}, 11) is None
    result = resolve("copy that", wm, {}, 11, llm=forbidden_llm)
    assert result.path == "none"
    assert result.text == "copy that"
    assert not result.changed
    assert calls == []


def test_that_after_a_comms_verb_is_a_conjunction_with_a_clause():
    wm = _memory("open_app", {"app": "Messages"})
    assert detect(
        "message Noah that yoga's moved to sunday morning", wm, {}, 11
    ) is None
    assert detect("send that to priya", wm, {}, 11) == "pronoun"


def test_llm_is_gated_for_site_search_irreversible_and_empty_context():
    calls = []

    def forbidden_llm(*args):
        calls.append(args)
        raise AssertionError("gated rewrite reached the LLM")

    no_site = _memory("open_app", {"app": "Finder"}, resolved="open Finder")
    result = resolve(
        "search for best podcasts", no_site, {"app": "Finder"}, 11,
        llm=forbidden_llm)
    assert result.path == "none"
    assert result.reason == "llm-gated"

    no_person = _memory("open_url", {"url": "https://example.com"})
    result = resolve("send him a message", no_person, {}, 11,
                     llm=forbidden_llm)
    assert result.path == "none"
    assert result.reason == "llm-gated"

    stale = llm_rewrite(
        "open it", WorkingMemory(), {}, 11, forbidden_llm)
    assert stale.path == "none"
    assert stale.reason == "llm-gated"
    assert calls == []


def test_llm_rewrite_validator_preserves_content_and_context_referents():
    recent = "Recent: create_event title=Carpool with Priya start=monday 8am"
    assert _valid(
        "make it tuesday instead",
        "add a carpool with Priya at 8 am tuesday",
        recent)
    assert not _valid(
        "make it tuesday instead",
        "add a carpool with Priya at 8 am wednesday",
        recent)
    assert not _valid(
        "open it", "open the budget spreadsheet",
        "Focus: app=Finder\nRecent: open_file path=report.pdf")
    assert _valid("hyde it", "hide Music", "Focus: app=Music")
    assert _valid(
        "set a timer for seven thirty",
        "set a timer for 7:30",
        "Recent: start_timer duration=30 minutes")


def test_again_after_redacted_communication_asks_for_details():
    message = _memory(
        "send_message", {"to": "Arda", "body": "private"},
        resolved="send message to Arda")
    result = resolve("again", message, {}, 11, catalog=_Catalog())
    assert result.path == "ask"
    assert result.ask == "What should I send, and to whom?"


def test_llm_fallback_parses_results_and_guard_rejects_new_irreversible_verb():
    wm = _memory("web_search", {"query": "history"})
    calls = []

    def llm_output(value):
        def call(prompt, tokens):
            calls.append((prompt, tokens))
            return value
        return call

    unchanged = resolve("the second one", wm, {}, 11,
                        llm=llm_output("UNCHANGED"))
    assert unchanged.path == "none"
    assert not unchanged.changed

    ask = resolve("the second one", wm, {}, 11,
                  llm=llm_output("ASK: Which one?"))
    assert ask.path == "ask"
    assert ask.ask == "Which one?"

    rewritten = resolve("the second one", wm, {}, 11,
                        llm=llm_output("show the second"))
    assert rewritten.path == "llm"
    assert rewritten.text == "show the second"
    assert calls[-1][1] == 40

    unsafe = resolve("open it", wm, {}, 11,
                     llm=llm_output("delete report.pdf"))
    assert unsafe.path == "none"
    assert unsafe.reason == "guard"
    assert unsafe.text == "open it"


def test_llm_is_not_called_without_followup_detection():
    wm = _memory("open_url", {"url": "https://example.com"})

    def fail_if_called(*_):
        raise AssertionError("fast path called the LLM")

    result = resolve("open Safari", wm, {}, 11, llm=fail_if_called)
    assert result.path == "none"
    assert detect("open Safari", wm, {}, 11) is None


def test_history_privacy_atomic_save_and_compact_recent_lines(tmp_path):
    path = tmp_path / "memory" / "working.json"
    wm = WorkingMemory(path=path)
    wm.record("send message to Mom saying TOP SECRET",
              "send message to Mom saying TOP SECRET", "send_message",
              {"to": "Mom", "body": "TOP SECRET", "text": "TOP SECRET",
               "message": "TOP SECRET"},
              True, {"app": "Messages"}, t=1)
    wm.record("type a secret", "type a secret", "type_text",
              {"text": "TOP SECRET"}, True, {"app": "Notes"}, t=2)
    assert path.exists()
    saved = path.read_text()
    assert "TOP SECRET" not in saved
    assert wm.turns[0].args["body"] == "TOP SECRET"
    assert wm.turns[1].args["text"] == "TOP SECRET"
    assert len(wm.recent_lines(now=3)) == 2
    assert all(len(line) <= 80 for line in wm.recent_lines(now=3))
    assert "TOP SECRET" not in "\n".join(wm.recent_lines(now=3))
    assert "TOP SECRET" in "\n".join(wm.recent_detail_lines(now=3))
    assert wm.recent_lines(0, now=3) == []

    history = [{
        "utterance": "navigate",
        "ctx": {"app": "Zen", "t": 5},
        "outcome": {"skill": "open_url",
                    "args": {"url": "https://en.wikipedia.org/"},
                    "ok": True},
    }]
    restored = WorkingMemory.from_history(history, {"t": 6})
    assert restored.last(6).t == 5
    assert restored.focus(6, {"app": "Zen"})["site"] == "wikipedia.org"


def test_all_search_templates_exist_and_adapter_shape():
    assert len(SEARCH_URLS) == 30
    assert STATIC.count("Output:") == 8
    assert STATIC.count("Output: UNCHANGED") == 2
    assert "Output: ASK:" in STATIC
    adapter = eval_adapter("open Safari", {"app": "Zen", "t": 11}, [])
    assert set(adapter) == {"text", "changed", "path", "ask", "ms"}
    assert adapter["text"] == "open Safari"
    assert adapter["path"] == "none"
    assert isinstance(adapter["ms"], float)


def test_fast_path_microbenchmarks():
    now = 20.0
    wm = _memory("open_url", {"url": "https://en.wikipedia.org/"}, t=now)
    utterances = ["open Safari"] * 200
    adapter_samples = []
    detect_samples = []
    history = [{
        "utterance": "navigate to Wikipedia",
        "ctx": {"app": "Zen", "t": now},
        "outcome": {"skill": "open_url",
                    "args": {"url": "https://en.wikipedia.org/"},
                    "ok": True},
    }]
    for utterance in utterances:
        start = time.perf_counter()
        eval_adapter(utterance, {"app": "Zen", "t": now}, history)
        adapter_samples.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        detect(utterance, wm, {"app": "Zen"}, now)
        detect_samples.append((time.perf_counter() - start) * 1000)
    assert statistics.median(adapter_samples) < 2
    assert statistics.median(detect_samples) < 1


def _live_history(utterance, app, skill, args, url=None):
    ctx = {"app": app, "t": 0}
    if url:
        ctx["url"] = url
    return [{"utterance": utterance, "ctx": ctx,
             "outcome": {"skill": skill, "args": args, "ok": True}}]


def test_live_self_contained_relative_volume_stays_unchanged():
    history = _live_history("turn the volume up", "Music", "change_volume",
                            {"delta": 10})
    for text in ("make it way louder", "a lot quieter", "much brighter"):
        result = eval_adapter(text, {"app": "Music", "t": 5}, history)
        assert not result["changed"], text
    result = eval_adapter("a lot more", {"app": "Music", "t": 5}, history)
    assert result["changed"] and "a lot" in result["text"]


def test_live_explicit_target_blocks_site_scoping():
    wiki = "https://en.wikipedia.org/wiki/History"
    history = _live_history("search wikipedia for history", "Zen",
                            "open_url", {"url": wiki}, url=wiki)
    ctx = {"app": "Zen", "url": wiki, "t": 10}
    for text in ("search for flights to tokyo in safari",
                 "search for flights to tokyo on google",
                 "look up cat videos on youtube",
                 "search for tokyo hotels on kayak.com"):
        result = eval_adapter(text, ctx, history)
        assert not result["changed"], text
    assert eval_adapter("search for tokyo", ctx, history)["changed"]


def test_live_questions_are_not_site_scoped():
    wiki = "https://en.wikipedia.org/wiki/History"
    history = _live_history("search wikipedia for history", "Zen",
                            "open_url", {"url": wiki}, url=wiki)
    ctx = {"app": "Zen", "url": wiki, "t": 10}
    for text in ("look up when the golden gate bridge opened",
                 "search for how tall mount everest is",
                 "look up who wrote dune",
                 "find out what time the store closes"):
        result = eval_adapter(text, ctx, history)
        assert not result["changed"], text
