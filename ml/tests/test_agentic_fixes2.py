import time

from brain.agentic import content, hint
from brain.app_hints import match_hints
from brain.catalog import Catalog
from brain.dsl import valid_predicate
from brain.finish import evidence
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeServer
from test_planner_loop import FakePlanner, run, trace_for
from test_planner_verify import VerifyPlanner


class CapturingTracer(Tracer):
    def finish(self, outcome):
        self.last = self.current
        super().finish(outcome)


def _orch(server=None, planner=None, tracer=None):
    orch = Orchestrator(server or FakeServer(), Catalog.load(),
                        tracer or Tracer())
    orch.planner = planner
    orch.LOAD_POLL_S, orch.LOAD_WAIT_S = 0.001, 0.1
    return orch


def test_content_hints_and_repeated_content_ask():
    args = {"about": "I can do Thursday at three", "reply": True}
    value = "I can do Thursday at three"
    assert content(args) == value
    assert f'type exactly: "{value}"' in hint("draft_email", args)
    assert "type exactly:" not in hint("compose_text", {"topic": value})

    question = "What text should I write in the reply?"
    planner = FakePlanner([[f'ask "{question}"'], [f'ask "{question}"']])
    orch = _orch(planner=planner)
    orch._agentic = {"skill": "draft_email", "args": args}
    trace = trace_for(orch, "draft a reply to this email")

    assert run(orch._planner_loop(trace["utterance"], trace)) == "awaiting_user"
    assert "ask rejected: the text is: " + f'"{value}" — type it' in \
        "\n".join(planner.user_msgs[1]["last_batch"])
    assert not any("loop_guard" in d for d in trace["decisions"])
    assert not any("planner.recover" in d for d in trace["decisions"])
    assert orch._recover_round == 0


def test_invalid_expect_is_dropped_but_action_executes():
    planner = FakePlanner([
        ["press #1181", 'expect radio "Timers" checked'],
        ['done "ok"'],
    ])
    server = FakeServer()
    orch = _orch(server, planner)
    trace = trace_for(orch)
    trace.update(rpc=[], stages={})
    orch.tracer.current = trace

    assert valid_predicate(' title~"Timers" ') == 'title~"Timers"'
    assert valid_predicate('radio "Timers" checked') is None
    assert run(orch._planner_loop("press the timer radio", trace)) == "ok"
    act = next(params for method, params in server.rpcs if method == "act")
    assert act["op"] == "press" and act["ref"] == 1181
    assert "expect" not in act
    assert {"expect_dropped": {
        "expect": 'radio "Timers" checked', "action": "press #1181"}} \
        in trace["decisions"]


def test_app_change_supersedes_pending_task_and_same_app_answer_resumes(
        tmp_path):
    utterance = "can you trim this video to be 5 seconds"
    assert [h.id for h in match_hints(utterance, "Adobe Premiere")] == [
        "premiere"]

    tracer = CapturingTracer(tmp_path / "traces")
    orch = _orch(tracer=tracer)
    orch.engine = object()
    orch._pending_task = {
        "goal": "play lofi on spotify", "app": "Spotify", "t": time.time()}
    planned = []

    async def planner_loop(goal, trace, answer=None):
        planned.append((goal, answer))
        return "planned"

    async def engine_route(text, trace):
        return await planner_loop(text, trace)

    orch._planner_loop = planner_loop
    orch._engine_route = engine_route
    result = run(orch.handle_utterance(utterance, {"app": "Adobe Premiere"}))
    assert result["outcome"] == "planned"
    assert planned == [(utterance, None)]
    decision = next(
        d["pending_superseded"] for d in tracer.last["decisions"]
        if "pending_superseded" in d)
    assert decision["by"] == "app_changed"
    assert decision["goal"] == "play lofi on spotify"

    resumed = []
    same = _orch()
    same._pending_task = {
        "goal": "play lofi on spotify", "app": "Spotify", "t": time.time()}

    async def resume(goal, trace, answer=None):
        resumed.append((goal, answer))
        return "resumed"

    same._planner_loop = resume
    assert run(same.handle_utterance("Thursday", {"app": "Spotify"}))[
        "outcome"] == "resumed"
    assert resumed == [("play lofi on spotify", "Thursday")]


def test_youtube_watch_page_is_play_evidence():
    watch = "https://www.youtube.com/watch?v=abc"
    assert evidence("play", "lofi", obs={
        "url": watch,
        "window": "Lofi Girl - beats to relax - YouTube",
    })
    assert not evidence("play", "lofi", obs={
        "url": "https://www.youtube.com/results?search_query=lofi",
        "window": "lofi - YouTube",
    })
    assert not evidence("play", "lofi", obs={
        "url": "https://www.youtube.com/results?search_query=lofi",
        "window": "lofi - YouTube",
    }, url=watch)


def test_youtube_watch_page_auto_completes_after_press():
    state = {"playing": False}

    def observe():
        if state["playing"]:
            url = "https://www.youtube.com/watch?v=abc"
            title = "Lofi Girl - beats to relax - YouTube"
        else:
            url = "https://www.youtube.com/results?search_query=lofi"
            title = "lofi - YouTube"
        return {
            "epoch": 1, "app": "Google Chrome", "window": title,
            "url": url, "elements": [],
            "text": f'app: Google Chrome | window: "{title}"',
        }

    def act(params):
        state["playing"] = True
        return {"ok": True, "epoch": 2}

    server = FakeServer(act=act, observe=observe)
    planner = FakePlanner([["press #5"]])
    orch = _orch(server, planner)
    trace = trace_for(orch, "play lofi on youtube")

    assert run(orch._planner_loop(trace["utterance"], trace)) == "ok"
    assert state["playing"]
    assert any("auto_done" in decision for decision in trace["decisions"])
    assert planner.calls == 1, trace["decisions"]


def test_bare_site_titles_are_loading_and_repoll(tmp_path):
    orch = _orch()
    for title in ("(2) YouTube", "YouTube"):
        assert orch._page_loading({
            "app": "Google Chrome", "window": title,
            "url": "https://www.youtube.com",
        })
    assert not orch._page_loading({
        "app": "Google Chrome", "window": "Lofi Girl - YouTube",
        "url": "https://www.youtube.com",
    })

    state = {"verifies": 0}

    def verify(_params):
        state["verifies"] += 1
        return {"ok": state["verifies"] > 1,
                "observed": 'title "(2) YouTube"'}

    server = FakeServer(
        handlers={"verify": verify},
        observe=lambda: {
            "epoch": 1, "app": "Google Chrome", "window": "(2) YouTube",
            "url": "https://www.youtube.com",
            "text": 'app: Google Chrome | window: "(2) YouTube"',
            "elements": [],
        })
    planner = VerifyPlanner([
        ['url "https://www.youtube.com/results?search_query=lofi"',
         'expect title~"Lofi"'],
        ['done "ok"'],
    ])
    orch = _orch(server, planner)
    trace = trace_for(orch, "search youtube for lofi")
    assert run(orch._planner_loop(trace["utterance"], trace)) == "ok"
    assert state["verifies"] == 2
    assert not any("loop_guard" in d for d in trace["decisions"])


def test_style_about_is_composed_literal_about_is_typed():
    funny = hint("draft_email", {"about": "is funny", "reply": "true"})
    assert "type exactly" not in funny and "your own words (funny)" in funny
    assert content({"about": "something funny"}) is None
    literal = hint("draft_email", {"about": "I can do Thursday at three"})
    assert 'type exactly: "I can do Thursday at three"' in literal
