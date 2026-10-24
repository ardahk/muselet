import json
import statistics
import time

from brain.memory import WorkingMemory, detect, eval_adapter, resolve
from brain.memory.rewrite import STATIC
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


def test_person_and_item_substitution_never_invent_referents():
    person = _memory("send_message",
                     {"to": "Mom", "body": "I'm late"},
                     resolved="send message to Mom")
    result = resolve("send her a message saying hi", person, {}, 11)
    assert result.changed
    assert "Mom" in result.text
    assert person.last(11).args == {"to": "Mom"}

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

    for utterance in ("a bit more", "louder"):
        assert detect(utterance, change, {}, 11) == "refinement"
        assert resolve(utterance, change, {}, 11).changed


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
                        llm=llm_output("open Wikipedia"))
    assert rewritten.path == "llm"
    assert rewritten.text == "open Wikipedia"
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
    assert wm.turns[0].args == {"to": "Mom"}
    assert wm.turns[1].args == {}
    assert len(wm.recent_lines(now=3)) == 2
    assert all(len(line) <= 80 for line in wm.recent_lines(now=3))
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
    assert len(SEARCH_URLS) == 27
    assert STATIC.count("Output:") == 6
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
