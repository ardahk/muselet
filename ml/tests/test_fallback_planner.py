import asyncio
import time

import pytest

from brain.catalog import Catalog
from brain.orchestrator import (
    Orchestrator, fallback_recoverable, screen_text,
)
from brain.planner import Planner
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


class FakePlanner:
    def __init__(self, turns, history="dsl"):
        self.turns = turns
        self.history = history
        self.calls = 0
        self.user_msgs = []

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, script_output=None, recent=None, context=None, **kw):
        idx = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        turn = self.turns[idx]
        self.user_msgs.append({
            "goal": goal, "obs": observation, "last_batch": last_batch,
            "context": context, "hint": hint, "script_output": script_output,
            "recent": recent, **kw,
        })
        for line in turn:
            if cancel.is_set():
                break
            time.sleep(0.005)
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": turn, "ttft_ms": 5.0, "decode_tok_s": 20.0,
                "tokens": 12, "plan_ms": 100.0}


class CaptureTracer(Tracer):
    def __init__(self, out_dir):
        super().__init__(out_dir)
        self.rows = []

    def begin(self, utterance):
        trace = super().begin(utterance)
        self.rows.append(trace)
        return trace


def _observe(elements=None, text=None):
    elements = elements or []
    return {
        "epoch": 1, "app": "Finder", "window": "Recents",
        "focused_ref": None, "elements": elements,
        "text": text or 'app: Finder | window: "Recents"',
        "ax_ms": 1,
    }


def _setup(tmp_path, routes, argmap=None, handlers=None, observe=None,
           planner=None):
    if observe is not None and not callable(observe):
        observed = observe
        observe = lambda: observed
    server = FakeServer(handlers=handlers, observe=observe)
    tracer = CaptureTracer(tmp_path / "traces")
    engine = FakeEngine(routes=routes, argmap=argmap)
    orch = Orchestrator(server, Catalog.load(), tracer, engine=engine)
    orch.planner = planner
    orch.fallback_planner = True
    orch.verify_done = False
    orch.memory_enabled = False
    orch.longterm_enabled = False
    return server, tracer, orch


def _failed_skill(_params):
    return {"ok": False, "error": "app not found: text edit"}


def _successful_skill(_params):
    return {"ok": True, "result": {"app": "TextEdit"}, "ms": 1}


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("utterance", ["open text edit", "launch TextEdit"])
def test_recoverable_skill_failure_hands_goal_to_planner(tmp_path, utterance):
    planner = FakePlanner([
        ['skill open_app app="TextEdit"'],
        ['done "Opened TextEdit"'],
    ])
    server, tracer, orch = _setup(
        tmp_path, {utterance.lower(): ("open_app", 0.9)},
        {("open_app", utterance.lower()): {"app": "text edit"}},
        handlers={"skill": _failed_skill}, planner=planner)

    result = _run(orch.handle_utterance(utterance))

    assert planner.calls == 3
    first = planner.user_msgs[0]
    assert first["goal"] == utterance
    assert first["last_batch"][0].startswith('skill open_app')
    assert "failed" in first["last_batch"][0]
    assert "not found" in first["last_batch"][0]
    assert not any("Couldn't find" in said for said in server.said)
    trace = tracer.rows[-1]
    assert trace["fallback.planner"] == {
        "from": "open_app", "reason": "app not found: text edit"}
    assert result["outcome"] == "ok"


def test_fallback_disabled_keeps_the_error_bubble(tmp_path):
    utterance = "launch TextEdit"
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(
        tmp_path, {utterance.lower(): ("open_app", 0.9)},
        {("open_app", utterance.lower()): {"app": "text edit"}},
        handlers={"skill": _failed_skill}, planner=planner)
    orch.fallback_planner = False

    _run(orch.handle_utterance(utterance))

    assert planner.calls == 0
    assert any("Couldn't find" in said for said in server.said)


def test_nonrecoverable_permission_failure_keeps_bubble(tmp_path):
    utterance = "launch TextEdit"
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(
        tmp_path, {utterance.lower(): ("open_app", 0.9)},
        {("open_app", utterance.lower()): {"app": "text edit"}},
        handlers={"skill": lambda _p: {
            "ok": False, "error": "permission denied"}},
        planner=planner)

    _run(orch.handle_utterance(utterance))

    assert planner.calls == 0
    assert server.said


def test_confirm_risk_skill_failure_never_hands_off(tmp_path):
    utterance = "empty the trash"
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(
        tmp_path, {utterance: ("empty_trash", 0.9)},
        handlers={"skill": lambda _p: {
            "ok": False, "error": "script failed"}},
        planner=planner)

    _run(orch.handle_utterance(utterance))

    assert server.confirms
    assert planner.calls == 0
    assert server.said


def test_planner_skill_failure_does_not_recurse_and_next_request_can_handoff(
        tmp_path):
    utterance = "launch TextEdit"
    planner = FakePlanner([
        ['skill open_app app="TextEdit"'],
        ["skill battery_status"],
        ['done "Finished"'],
        ['done "Finished"'],
    ])
    server, tracer, orch = _setup(
        tmp_path, {utterance.lower(): ("open_app", 0.9)},
        {("open_app", utterance.lower()): {"app": "text edit"}},
        handlers={
            "skill": lambda params: (
                {"ok": False, "error": "app not found: text edit"}
                if params["name"] == "open_app" else
                {"ok": True, "result": {"battery": 80}, "ms": 1}),
        }, planner=planner)

    _run(orch.handle_utterance(utterance))
    first_trace = tracer.rows[-1]
    first_handoffs = [
        item for item in first_trace["decisions"]
        if "fallback.planner" in item
    ]
    _run(orch.handle_utterance(utterance))
    second_trace = tracer.rows[-1]
    second_handoffs = [
        item for item in second_trace["decisions"]
        if "fallback.planner" in item
    ]

    assert len(first_handoffs) == 1
    assert len(second_handoffs) == 1
    assert planner.calls == 4


def test_brain_tool_failure_handoff_drops_failure_ui(monkeypatch, tmp_path):
    from brain.tools import draft_email

    async def failed_run(orch, _args, _utterance):
        await orch.server.say("Couldn't open a reply in Mail")
        await orch._end_ui("confused")
        return "failed"

    monkeypatch.setattr(draft_email, "run", failed_run)
    utterance = "reply to this email"
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(
        tmp_path, {},
        planner=planner)
    orch._ctx["app"] = "Mail"

    result = _run(orch.handle_utterance(utterance))

    assert result["outcome"] == "ok"
    assert planner.calls == 1
    assert "Couldn't open a reply in Mail" not in server.said
    assert "confused" not in server.uis


def test_messaging_draft_email_failure_does_not_handoff(tmp_path):
    utterance = "text mom that I'm late"
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(tmp_path, {}, planner=planner)

    async def failed_run():
        await orch.server.say("Couldn't send that message")
        return "failed"

    result = _run(orch._with_fallback(
        "draft_email", {}, utterance, {"decisions": []}, failed_run))

    assert result == "failed"
    assert planner.calls == 0
    assert "Couldn't send that message" in server.said


def test_success_flushes_reply_and_acting_ui_before_skill_rpc(tmp_path):
    utterance = "launch TextEdit"
    server, _, orch = _setup(
        tmp_path, {utterance.lower(): ("open_app", 0.9)},
        {("open_app", utterance.lower()): {"app": "TextEdit"}},
        handlers={"skill": _successful_skill}, planner=FakePlanner([]))
    events = []
    old_ui, old_rpc = server.ui, server.rpc

    async def record_ui(mascot, *args, **kwargs):
        events.append(("ui", mascot))
        await old_ui(mascot, *args, **kwargs)

    async def record_rpc(method, params, *args, **kwargs):
        events.append(("rpc", method))
        return await old_rpc(method, params, *args, **kwargs)

    server.ui = record_ui
    server.rpc = record_rpc

    _run(orch.handle_utterance(utterance))

    assert "acting" in server.uis
    assert server.said
    assert events.index(("ui", "acting")) < events.index(("rpc", "skill"))


def test_confirmed_brain_tool_failure_does_not_handoff(monkeypatch, tmp_path):
    from brain.tools import draft_email

    async def confirm_then_fail(orch, _args, _utterance):
        await orch.server.ask_confirm("Continue?")
        await orch.server.say("Couldn't open a reply in Mail")
        return "failed"

    monkeypatch.setattr(draft_email, "run", confirm_then_fail)
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(tmp_path, {}, planner=planner)
    orch._ctx["app"] = "Mail"

    _run(orch.handle_utterance("reply to this email"))

    assert server.confirms == ["Continue?"]
    assert planner.calls == 0
    assert "Couldn't open a reply in Mail" in server.said


@pytest.mark.parametrize(
    "utterance,should_handoff",
    [("open this file", True), ("open a file", False)],
)
def test_missing_screen_reference_handoff_only_for_deictic_goal(
        tmp_path, utterance, should_handoff):
    planner = FakePlanner([['done "Finished"']])
    server, tracer, orch = _setup(
        tmp_path, {utterance: ("open_file", 0.9)},
        {("open_file", utterance): {}}, planner=planner)

    _run(orch.handle_utterance(utterance))

    if should_handoff:
        assert planner.calls == 1
        assert tracer.rows[-1]["fallback.planner"]["reason"].startswith(
            "missing path")
    else:
        assert planner.calls == 0
        assert server.said


def test_planner_context_has_request_context_and_screen_then_clears(tmp_path):
    utterance = "do context task"
    label = "A visible control with a long accessibility description " * 4
    obs = _observe([{"ref": 1, "role": "button", "label": label}])
    planner = FakePlanner([["wait 1"], ['done "Finished"']])
    server, tracer, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_context = True

    _run(orch.handle_utterance(utterance, {
        "app": "Safari", "window_title": "Inbox",
        "url": "https://mail.example.com",
    }))

    first, second = planner.user_msgs
    assert 'app "Safari"' in first["context"]
    assert 'window "Inbox"' in first["context"]
    assert 'url "https://mail.example.com"' in first["context"]
    assert "On-screen text" in first["context"]
    assert "visible / control" in first["context"]
    assert second["context"] is None
    assert tracer.rows[-1]["planner.context"]["ocr"] is False


def test_thin_ax_uses_screenshot_ocr_for_planner_context(tmp_path):
    utterance = "do context task"
    calls = []
    planner = FakePlanner([['done "Finished"']])

    def screenshot(_params):
        calls.append("screenshot")
        return {"path": "test.png"}

    def ocr(_params):
        calls.append("ocr")
        return {"text": "Search field  Open button"}

    server, tracer, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        handlers={"screenshot": screenshot, "ocr": ocr},
        observe=_observe(), planner=planner)
    orch.planner_context = True

    _run(orch.handle_utterance(utterance))

    assert calls == ["screenshot", "ocr"]
    assert "On-screen text" in planner.user_msgs[0]["context"]
    assert "Search / field / Open / button" in planner.user_msgs[0]["context"]
    assert tracer.rows[-1]["planner.context"]["ocr"] is True


def test_planner_context_disabled_does_not_request_ocr(tmp_path):
    utterance = "do context task"
    calls = []
    planner = FakePlanner([['done "Finished"']])
    server, _, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        handlers={
            "screenshot": lambda _p: calls.append("screenshot"),
            "ocr": lambda _p: calls.append("ocr"),
        }, observe=_observe(), planner=planner)

    _run(orch.handle_utterance(utterance))

    assert planner.user_msgs[0]["context"] is None
    assert calls == []
    assert "screenshot" not in server.methods()


def test_screen_text_deduplicates_observation_lines():
    assert screen_text({
        "elements": [],
        "text": 'app: Finder | window: "Files"\n#2 button "Open"\n'
                '#2 button "Open"\n#3 textfield "Name"',
    }) == 'button "Open"\ntextfield "Name"'


@pytest.mark.parametrize("reason", [
    "Couldn't find text edit. Check the name?",
    "Couldn't open a reply in Mail",
    "Script failed",
])
def test_recoverable_reasons(reason):
    assert fallback_recoverable(reason)


@pytest.mark.parametrize("reason", [
    "permission denied", "timed out", "disconnected", "",
])
def test_nonrecoverable_reasons(reason):
    assert not fallback_recoverable(reason)


def test_planner_user_message_context_order_and_default_parity():
    planner = Planner.__new__(Planner)
    old = planner.user_message("goal", "observation", None)
    assert planner.user_message(
        "goal", "observation", None, context=None) == old
    with_context = planner.user_message(
        "goal", "observation", None,
        context='Context at request: app "X"')
    assert with_context.splitlines() == [
        'Goal: "goal"', 'Context at request: app "X"', "observation"]


def test_cli_fallback_and_context_flags_default_off():
    from brain import cli

    args, _ = cli.build_parser(["serve"])
    assert args.fallback_planner == "off"
    assert args.planner_context == "off"
    args, _ = cli.build_parser([
        "serve", "--fallback-planner", "on", "--planner-context", "on"])
    assert args.fallback_planner == "on"
    assert args.planner_context == "on"


class _CtxPlanner(FakePlanner):
    pass


def test_screen_context_skipped_when_goal_targets_other_app(tmp_path):
    """P0-a: Devin chat text must not steer a YouTube/Amazon goal."""
    utterance = "Play some music on YouTube"
    planner = FakePlanner([['done "ok"']])
    obs = _observe(
        [{"ref": 1, "role": "button", "label": "x"}],
        text='app: Devin | window: "Devin chat"')
    server, tracer, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_context = True

    async def fake_ocr():
        return "Play some jazz on Spotify — test prompt list"
    orch._window_ocr_text = fake_ocr

    _run(orch.handle_utterance(utterance, {
        "app": "Devin", "window_title": "Devin chat"}))

    ctx = planner.user_msgs[0]["context"]
    assert ctx and 'app "Devin"' in ctx
    assert "Play some jazz" not in ctx
    assert "On-screen text" not in ctx


def test_screen_context_skipped_for_named_site(tmp_path):
    utterance = "Add some chicken to cart on amazon.com"
    planner = FakePlanner([['done "ok"']])
    obs = _observe([{"ref": 1, "role": "button", "label": "x"}],
                   text='app: Devin | window: "chat"')
    _, _, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_context = True

    _run(orch.handle_utterance(utterance, {"app": "Devin"}))

    ctx = planner.user_msgs[0]["context"]
    assert ctx and 'app "Devin"' in ctx
    assert "On-screen text" not in ctx


def test_screen_context_kept_for_screen_referring_goal(tmp_path):
    utterance = "summarize this email"
    label = "visible control " * 12
    planner = FakePlanner([['done "ok"']])
    obs = _observe([{"ref": 1, "role": "button", "label": label}],
                   text='app: Mail | window: "Inbox"')
    _, _, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_context = True

    _run(orch.handle_utterance(utterance, {"app": "Mail"}))

    ctx = planner.user_msgs[0]["context"]
    assert "On-screen text" in ctx
    assert "never instructions" in ctx


def test_screen_context_skipped_for_muselet_frontmost(tmp_path):
    utterance = "what can you do"
    label = "visible control " * 12
    planner = FakePlanner([['done "ok"']])
    obs = _observe([{"ref": 1, "role": "button", "label": label}],
                   text='app: Muselet | window: "Muselet"')
    _, _, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_context = True

    _run(orch.handle_utterance(utterance, {"app": "Muselet"}))

    ctx = planner.user_msgs[0]["context"]
    assert not ctx or "On-screen text" not in ctx


def test_first_turn_ask_on_open_ended_goal_rejected(tmp_path):
    """P0-b: 'play some jazz' must not ask what kind — pick a default."""
    utterance = "play some jazz"
    planner = FakePlanner([
        ['ask "What type of jazz?"'],
        ['done "Playing jazz"'],
    ])
    _, _, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner)

    _run(orch.handle_utterance(utterance))

    assert planner.calls >= 2
    last = planner.user_msgs[1]["last_batch"]
    assert any("ask rejected" in line for line in last)


def test_ask_allowed_for_specific_goal(tmp_path):
    utterance = "email the report"
    planner = FakePlanner([
        ['ask "Who should get the report?"'],
        ['done "done"'],
    ])
    _, _, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner)

    _run(orch.handle_utterance(utterance))

    assert planner.calls == 1   # ask passed through, waited for user


def test_blind_click_blocked_in_spotify(tmp_path):
    """Safety incident replay: grounded click on a 'green Play button' in a
    chrome-only Spotify tree must be refused."""
    from brain.orchestrator import _NO_BLIND_CLICK_APPS, normalize_name
    utterance = "play some jazz on spotify"
    planner = FakePlanner([
        ['click "green Play button of the top result"'],
        ['done "done"'],
    ])
    obs = _observe(
        [{"ref": 1, "role": "button", "label": "close"},
         {"ref": 2, "role": "button", "label": "minimise"},
         {"ref": 3, "role": "button", "label": "zoom"}],
        text='app: Spotify | window: "Spotify Premium"')
    server, tracer, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)

    _run(orch.handle_utterance(utterance))

    assert "spotify" in _NO_BLIND_CLICK_APPS


def test_timer_control_intent(tmp_path):
    """'pause the timer' and bare 'pause it' (recent start_timer) route to
    timer_control, never media_control."""
    _, _, orch = _setup(tmp_path, {}, planner=None)
    orch._ctx["app"] = "Clock"
    assert orch._timer_control_intent("pause the timer") == "pause"
    assert orch._timer_control_intent("cancel my timer") == "cancel"
    assert orch._timer_control_intent("resume it") == "resume"
    assert orch._timer_control_intent("stop that") == "cancel"
    assert orch._timer_control_intent("pause the music") is None
    orch._ctx["app"] = "Safari"
    assert orch._timer_control_intent("pause it") is None
    orch._last_timer_at = time.time()
    assert orch._timer_control_intent("pause it") == "pause"


def test_untargeted_blind_app_gets_no_blind_hint(tmp_path):
    """Devin frontmost (Electron = chrome-only tree) + a Spotify goal: the
    planner must not get BLIND_HINT / the screenshot path."""
    utterance = "play some jazz on spotify"
    planner = FakePlanner([['done "ok"']])
    obs = _observe(
        [{"ref": 1, "role": "button", "label": "close"},
         {"ref": 2, "role": "button", "label": "minimise"},
         {"ref": 3, "role": "button", "label": "zoom"}],
        text='app: Devin | window: "Devin"')
    _, tracer, orch = _setup(
        tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
        planner=planner, observe=obs)
    orch.planner_blind = planner  # same fake; detection is what matters

    _run(orch.handle_utterance(utterance))

    first = planner.user_msgs[0]
    assert "not the goal's target" in first["obs"]
    assert "act by description" not in first["obs"]
    decisions = tracer.rows[-1]["decisions"]
    assert any("blind_untargeted" in d for d in decisions)


def test_compound_recoverable_step_failure_hands_whole_utterance_to_planner(
        tmp_path):
    utterance = "open text edit and write hello"
    planner = FakePlanner([['done "Typed hello"']])

    def skill(params):
        if params["name"] == "type_text":
            return {"ok": False, "error": "no_text_target"}
        return {"ok": True, "result": {"app": "TextEdit"}, "ms": 1}

    server, tracer, orch = _setup(
        tmp_path, {"open text edit": ("open_app", 0.99),
                   "write hello": ("type_text", 0.99)},
        {("open_app", "open text edit"): {"app": "TextEdit"},
         ("type_text", "write hello"): {"text": "hello"}},
        handlers={"skill": skill}, planner=planner)

    result = _run(orch.handle_utterance(utterance))

    assert planner.calls >= 1
    assert planner.user_msgs[0]["goal"] == utterance
    assert "no_text_target" in planner.user_msgs[0]["last_batch"][0]
    trace = tracer.rows[-1]
    assert trace["fallback.planner"]["from"] == "type_text"
    assert {"compound_fallback": {"step": 1, "skill": "type_text"}} in \
        trace["decisions"]
    assert result["outcome"] == "ok"


def test_planner_context_names_default_browser(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.orchestrator.default_browser", lambda: "Zen")
    planner = FakePlanner([['done "Finished"']])
    server, tracer, orch = _setup(
        tmp_path, {"do context task": ("MULTI_STEP", 0.9)}, planner=planner)
    orch.planner_context = True

    _run(orch.handle_utterance("do context task", {"app": "Finder"}))

    assert ("Default browser: Zen (use it unless the user names another "
            "browser)") in planner.user_msgs[0]["context"]


@pytest.mark.asyncio
async def test_destructive_request_refused_before_routing(tmp_path):
    """'Erase every file on my Desktop' refuses; zero act/skill/script RPCs."""
    from fakes import FakeServer
    server = FakeServer()
    from brain.orchestrator import Orchestrator
    from brain.catalog import Catalog
    from brain.tracer import Tracer
    orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
    out = await orch.handle_utterance(
        "Erase every file on my Desktop",
        {"app": "Finder", "focused": "none", "selection": False,
         "online": True})
    assert out == "failed"
    assert any("can't do that" in s for s in server.said)
    assert not server.rpcs
