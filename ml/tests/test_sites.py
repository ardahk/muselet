"""open_app / open_url resolution: site aliases and URL fixing, installed
native apps vs sites, spoken app names, named browsers, app fill from the
apps rpc, and same-tab navigation for browser page tasks."""

import asyncio
import time

import pytest

from brain.catalog import Catalog
from brain.decision import DecisionEngine
from brain.memory import WorkingMemory
from brain.orchestrator import Orchestrator, app_in, named_browser
from brain.planner import catalog_desc
from brain.sites import APP_SCHEMES, fix_url, normalize_name
from brain.traces import Tracer
from fakes import (FakeEngine, FakeServer, InlineWorker, ScriptedPlanner,
                   _skill_rpcs, _traces, run)


INSTALLED = ["Slack", "zoom.us", "Microsoft Teams", "Microsoft Outlook"]


def test_site_aliases_and_urls():
    assert normalize_name("The Google Docs website") == "googledocs"
    assert fix_url("gmail/inbox?x=1") == "https://mail.google.com/inbox?x=1"
    assert fix_url("https://github.com/a#b") == "https://github.com/a#b"
    assert fix_url("example/path") == "https://example.com/path"
    assert fix_url("localhost:3000/a") == "https://localhost:3000/a"
    assert fix_url("127.0.0.1:3000/a") == "https://127.0.0.1:3000/a"
    assert fix_url("[::1]:3000/a") == "https://[::1]:3000/a"


@pytest.mark.parametrize("scheme", APP_SCHEMES)
def test_fix_url_preserves_app_url_schemes(scheme):
    value = f" {scheme.upper()}:search:jazz "
    assert fix_url(value) == value.strip()


@pytest.mark.parametrize("scheme", [
    "tel", "facetime", "sms", "mailto", "javascript", "file",
])
def test_fix_url_does_not_pass_through_other_schemes(scheme):
    assert fix_url(f"{scheme}:123") == f"https://{scheme}.com:123"


@pytest.mark.parametrize("entry", ["skill", "planner", "execute"])
@pytest.mark.parametrize("app", ["Zoom", "Teams", "Outlook"])
@pytest.mark.parametrize("wording, web", [
    ("open {}", False), ("open {} website", True),
    ("go to {}", True), ("navigate to {}", True), ("open {}.com", True),
])
def test_brain29_installed_native_app_preferred(tmp_path, entry, app, wording, web):
    async def scenario():
        server = FakeServer(apps={"running": [], "installed": INSTALLED})
        orch = Orchestrator(server)
        text = wording.format(app)
        orch._utterance = text
        if entry == "skill":
            await orch._run_skill("open_app", {"app": app}, text, {"decisions": []})
            assert server.skills()[-1]["name"] == ("open_url" if web else "open_app")
        else:
            action = {"op": "open", "app": app}
            if entry == "planner":
                await orch._exec_one(action)
            else:
                await orch.execute_actions([action])
            acts = [p for method, p in server.rpcs if method == "act"]
            assert acts[-1]["op"] == ("url" if web else "open")
    asyncio.run(scenario())


@pytest.mark.parametrize("entry", ["skill", "planner", "execute"])
def test_brain29_apps_failure_does_not_rewrite_or_cache(entry):
    calls = []
    available = [False]

    def apps():
        calls.append(1)
        if not available[0]:
            raise RuntimeError("rpc timeout")
        return {"running": [], "installed": INSTALLED}

    async def scenario():
        server = FakeServer(apps=apps)
        orch = Orchestrator(server)
        orch._utterance = "open Slack"
        if entry == "skill":
            await orch._run_skill("open_app", {"app": "Slack"}, "open Slack", {"decisions": []})
            assert server.skills()[-1]["name"] == "open_app"
        elif entry == "planner":
            await orch._exec_one({"op": "open", "app": "Slack"})
        else:
            await orch.execute_actions([{"op": "open", "app": "Slack"}])
        assert not any(p.get("op") == "url" for m, p in server.rpcs if m == "act")
        assert orch._apps is None
        failed_calls = len(calls)
        available[0] = True
        assert await orch._app_names() == INSTALLED
        assert len(calls) == failed_calls + 1
    asyncio.run(scenario())


def test_known_empty_apps_allows_site_fallback():
    async def scenario():
        orch = Orchestrator(FakeServer())
        assert await orch._site_for_app("Slack", "open Slack") == ("slack", "slack.com")
    asyncio.run(scenario())


def test_missing_installed_list_does_not_allow_site_fallback():
    async def scenario():
        orch = Orchestrator(FakeServer(apps={"running": []}))
        assert await orch._site_for_app("Slack", "open Slack") is None
        assert orch._apps is None
    asyncio.run(scenario())


@pytest.mark.parametrize("entry", ["planner", "execute"])
def test_open_non_site_app_does_not_rewrite_from_goal(entry):
    async def scenario():
        server = FakeServer()
        orch = Orchestrator(server)
        orch._current_goal = "open notes and play lofi on youtube"
        action = {"op": "open", "app": "Notes"}
        if entry == "planner":
            await orch._exec_one(action)
        else:
            await orch.execute_actions([action])
        acts = [p for method, p in server.rpcs if method == "act"]
        assert acts == [{"op": "open", "app": "Notes"}]
    asyncio.run(scenario())


@pytest.mark.parametrize("entry", ["planner", "execute"])
def test_app_scheme_url_does_not_receive_browser_arg(entry):
    async def scenario():
        server = FakeServer()
        orch = Orchestrator(server)
        orch._current_goal = "play jazz on spotify in chrome"
        action = {"op": "url", "url": "spotify:search:jazz"}
        if entry == "planner":
            await orch._exec_action(action)
        else:
            await orch.execute_actions([action])
        acts = [params for method, params in server.rpcs if method == "act"]
        assert acts[-1]["url"] == "spotify:search:jazz"
        assert "browser" not in acts[-1]
    asyncio.run(scenario())


def _browser_orch(tmp_path, routes=None, args=None, planner=None):
    server = FakeServer()
    orch = Orchestrator(
        server, Catalog.load(), Tracer(tmp_path / "traces"),
        engine=FakeEngine(routes or {}, args or {}))
    orch.planner = planner
    return orch, server


# ---------- spoken app names (apps / notes regressions) ----------

@pytest.mark.parametrize("entry", ["skill", "planner", "execute"])
@pytest.mark.parametrize("spoken,expected", [
    ("text edit", "TextEdit"), ("face time", "FaceTime"),
    ("you tube music", "YouTube Music"), ("v s code", "Visual Studio Code"),
    ("vs code", "Visual Studio Code"), ("vscode", "Visual Studio Code"),
    ("chrome", "Google Chrome"), ("settings", "System Settings"),
    ("TextEdit", "TextEdit"), ("TextEdit.app", "TextEdit"),
])
def test_spoken_apps(entry, spoken, expected):
    async def scenario():
        server = FakeServer(apps={"installed": ["TextEdit", "FaceTime", "YouTube Music",
                                               "Visual Studio Code", "Google Chrome",
                                               "System Settings"], "running": []})
        orch = Orchestrator(server)
        orch._utterance = f"open {spoken}"
        if entry == "skill":
            await orch._run_skill("open_app", {"app": spoken}, orch._utterance,
                                  {"decisions": []})
            assert server.skills()[-1]["args"]["app"] == expected
        else:
            action = {"op": "open", "app": spoken}
            if entry == "planner":
                await orch._exec_one(action)
            else:
                await orch.execute_actions([action])
            assert [p for m, p in server.rpcs if m == "act"][-1]["app"] == expected
    asyncio.run(scenario())


@pytest.mark.parametrize("apps,expected", [
    ({"installed": ["Notes"], "running": []}, "awaiting_user"),
    ({"running": []}, "ok"),
    (lambda: (_ for _ in ()).throw(RuntimeError("unavailable")), "ok"),
])
def test_unknown_or_unavailable_apps(apps, expected):
    server = FakeServer(apps=apps)
    orch = Orchestrator(server)
    result = asyncio.run(orch._run_skill("open_app", {"app": "vscode"},
                                       "open vscode", {"decisions": []}))
    assert result == expected
    assert bool(server.skills()) == (expected == "ok")
    if expected == "awaiting_user":
        assert server.said == ["Which app?"]


def test_exact_compound_text_edit(tmp_path):
    engine = FakeEngine(
        routes={"open text edit": ("open_app", .99), "write hello": ("type_text", .99)},
        argmap={("open_app", "open text edit"): {"app": "text edit"},
                ("type_text", "write hello"): {"text": "hello"}})
    server = FakeServer(apps={"installed": ["TextEdit"], "running": []})
    orch = Orchestrator(server, engine=engine)
    result = asyncio.run(orch.handle_utterance("Open text edit and write hello"))
    assert result["outcome"] == "ok"
    assert server.skills()[0] == {"name": "open_app", "args": {"app": "TextEdit"}}
    assert server.skills()[1] == {"name": "type_text", "args": {"text": "hello"}}


# ---------- site and browser rewrites of open_app / open (first use) ----------

def test_site_and_browser_skill_rewrites():
    async def go():
        server = FakeServer()
        orch = Orchestrator(server, Catalog.load())
        trace = {"decisions": []}
        result = await orch._run_skill(
            "open_app", {"app": "Gmail"}, "navigate to gmail", trace)
        assert result == "ok"
        gmail = server.skills()[-1]
        assert gmail["name"] == "open_url"
        assert gmail["args"]["url"] == "https://mail.google.com"
        assert trace["site_switch"] == ["gmail", "mail.google.com"]

        server.apps = {"running": ["Slack.app"],
                       "installed": ["Safari", "Google Chrome"]}
        orch._apps = None
        orch._utterance = "open Slack"
        await orch._run_skill("open_app", {"app": "Slack"}, "open Slack",
                              {"decisions": []})
        assert server.skills()[-1]["name"] == "open_app"

        await orch._run_skill("open_app", {"app": "Safari"},
                              "search for cats", {"decisions": []})
        browser = server.skills()[-1]
        assert browser["name"] == "open_url"
        assert browser["args"]["url"] == "https://www.google.com"

        trace = {"decisions": []}
        orch._utterance = "open Safari"
        await orch._run_skill("open_app", {"app": "Safari"},
                              "open Safari", trace)
        assert server.skills()[-1]["name"] == "open_app"
        assert "browser_rewrite" not in trace

        orch._utterance = "open Chrome"
        await orch._run_skill("open_app", {"app": "Google Chrome"},
                              "open Chrome", {"decisions": []})
        assert server.skills()[-1]["name"] == "open_app"
    asyncio.run(go())


def test_planner_open_site_rewrites_to_url():
    async def go():
        server = FakeServer()
        orch = Orchestrator(server, Catalog.load())
        orch._current_goal = "navigate to gmail"
        result = await orch._exec_action({"op": "open", "name": "gmail"})
        assert result["status"] == "ok"
        assert server.rpcs[-1] == (
            "act", {"url": "https://mail.google.com", "op": "url"})
        assert orch._last_url == "https://mail.google.com"
    asyncio.run(go())


# ---------- named browsers reach browser skills and url acts (brain-9) ----------

def test_hidden_browser_args_stay_out_of_catalog_prompts():
    catalog = Catalog.load()
    engine = DecisionEngine.__new__(DecisionEngine)
    engine.catalog = catalog
    signature = lambda name: DecisionEngine.arg_signature(engine, name)
    assert signature("open_url") == "url:url required"
    assert signature("web_search") == "query:string required"
    lines = catalog_desc(catalog, signature).splitlines()
    expected = {
        "open_url": "open_url(url:url required): Open a URL in the default browser.",
        "web_search": "web_search(query:string required): Search the web for a query in the default browser.",
    }
    assert {line.split("(", 1)[0]: line for line in lines
            if line.startswith(("open_url(", "web_search("))} == expected
    assert catalog.validate_args("open_url", {
        "url": "https://example.com", "browser": "Safari"})["browser"] == "Safari"


def test_named_browser_aliases_and_context():
    assert named_browser("open this in Safari") == "Safari"
    assert named_browser("search for ramen in GOOGLE CHROME") == "Google Chrome"
    assert named_browser("use Chrome") == "Google Chrome"
    assert named_browser("open Firefox") == "Firefox"
    assert named_browser("using Microsoft Edge") == "Microsoft Edge"
    assert named_browser("open Brave Browser") == "Brave Browser"
    assert named_browser("search zen browser") == "Zen"
    assert named_browser("open with the Arc browser") == "Arc"
    assert named_browser("look it up in edge") == "Microsoft Edge"
    assert named_browser("use Brave") == "Brave Browser"
    assert named_browser("open a tab in Zen browser") == "Zen"
    assert named_browser("launch Vivaldi") == "Vivaldi"
    assert named_browser(
        "open in Arc, then use the Edge browser, then open Arc") == "Arc"
    assert named_browser("search for brave new world") is None
    assert named_browser("search for zen meditation") is None
    assert named_browser("look up opera tickets") is None


def test_planner_open_then_web_search_preserves_requested_browser(
        tmp_path, monkeypatch):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    text = "search for flights to tokyo in safari"
    planner = ScriptedPlanner([
        ['open "Safari"', 'skill web_search query="flights to Tokyo"'],
        ['done "ok"'],
    ])
    orch, server = _browser_orch(
        tmp_path, routes={text: ("MULTI_STEP", 0.95)}, planner=planner)
    asyncio.run(orch.handle_utterance(text))

    assert [p for m, p in server.rpcs if m == "skill"] == [{
        "name": "web_search",
        "args": {"query": "flights to Tokyo", "browser": "Safari"},
    }], server.rpcs
    open_rpc = next((i for i, (m, p) in enumerate(server.rpcs)
                     if m == "act" and p.get("op") == "open" and
                     p.get("name") == "Safari"), None)
    skill_rpc = next((i for i, (m, p) in enumerate(server.rpcs)
                      if m == "skill" and p.get("name") == "web_search"),
                     None)
    assert open_rpc is not None and skill_rpc is not None and \
        open_rpc < skill_rpc, server.rpcs


def test_planner_url_act_receives_named_browser(tmp_path):
    orch, server = _browser_orch(tmp_path)
    orch._current_goal = "open example.com in chrome"
    result = asyncio.run(orch._exec_action({
        "op": "url", "url": "https://example.com"}))
    assert result["status"] == "ok"
    assert next(p for m, p in server.rpcs if m == "act")["browser"] == \
        "Google Chrome"


@pytest.mark.parametrize(("text", "skill", "args", "browser"), [
    ("search for ramen in chrome", "web_search", {"query": "ramen"},
     "Google Chrome"),
    ("open github in arc", "open_url", {"url": "https://github.com"}, "Arc"),
    ("search for flights to tokyo", "web_search",
     {"query": "flights to tokyo"}, None),
])
def test_router_fast_path_browser_args(tmp_path, monkeypatch, text, skill,
                                       args, browser):
    import brain.planner as planner_module

    monkeypatch.setattr(planner_module, "worker", lambda: InlineWorker())
    orch, server = _browser_orch(
        tmp_path, {text: (skill, 0.95)}, {(skill, text): args})
    asyncio.run(orch.handle_utterance(text))
    rpc_args = next(p["args"] for m, p in server.rpcs
                    if m == "skill" and p["name"] == skill)
    if browser is None:
        assert "browser" not in rpc_args
    else:
        assert rpc_args["browser"] == browser


def test_execute_actions_url_receives_named_browser(tmp_path):
    orch, server = _browser_orch(tmp_path)
    orch._current_goal = "open example.com using the edge browser"
    assert asyncio.run(orch.execute_actions([{
        "op": "url", "url": "https://example.com"}])) == "ok"
    assert next(p for m, p in server.rpcs if m == "act")["browser"] == \
        "Microsoft Edge"


# ---------- open_app: app names from the apps rpc (brain-3) ----------

@pytest.mark.parametrize("text,names,want", [
    ("open chrome please", ["Google Chrome", "Safari"], "Google Chrome"),
    ("switch to google chrome", ["Google Chrome"], "Google Chrome"),
    ("launch premiere", ["Adobe Premiere Pro 2025"], "Adobe Premiere Pro 2025"),
    ("launch premiere", [], "Adobe Premiere Pro"),
    ("open safari", [], "Safari"),
    ("bring up finder", [], "Finder"),
    ("open visual studio code", ["Visual Studio Code", "Code"],
     "Visual Studio Code"),
    ("open textedit", ["TextEdit"], "TextEdit"),
    ("open the thing", ["Safari"], None),
])
def test_app_in(text, names, want):
    assert app_in(text, names) == want


def test_missing_app_filled_from_apps_rpc_and_cached(tmp_path):
    srv = FakeServer(apps={"running": [{"name": "Google Chrome", "pid": 1}],
                           "installed": ["Safari", "TextEdit"]})
    eng = FakeEngine(routes={"open chrome": ("open_app", 0.95),
                             "open textedit": ("open_app", 0.95)})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    assert run(o.handle_utterance("open chrome"))["outcome"] == "ok"
    assert run(o.handle_utterance("open textedit"))["outcome"] == "ok"
    assert _skill_rpcs(srv) == [("open_app", {"app": "Google Chrome"}),
                                ("open_app", {"app": "TextEdit"})]
    assert srv.methods().count("apps") == 1          # 60 s cache
    assert any({"app_fill": "Google Chrome"} in t["decisions"]
               for t in _traces(o.tracer))


def test_app_fill_survives_apps_rpc_failure(tmp_path):
    def boom():
        raise RuntimeError("hands offline")
    srv = FakeServer(apps=boom)
    eng = FakeEngine(routes={"open safari": ("open_app", 0.95)})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("open safari"))
    assert _skill_rpcs(srv) == [("open_app", {"app": "Safari"})]


def test_app_given_by_args_resolves_with_apps_rpc(tmp_path):
    srv = FakeServer()
    eng = FakeEngine(routes={"open safari": ("open_app", 0.95)},
                     argmap={("open_app", "open safari"): {"app": "Safari"}})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"), engine=eng)
    run(o.handle_utterance("open safari"))
    assert srv.methods().count("apps") == 1


# ---------- same-tab navigation and browser page tasks ----------

class _HintPlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = []

    def plan(self, goal, observation, last_batch, lines_out, loop,
             cancel, hint=None, script_output=None, recent=None):
        index = min(len(self.calls), len(self.turns) - 1)
        self.calls.append({"goal": goal, "hint": hint})
        lines = self.turns[index]
        for line in lines:
            if cancel.is_set():
                break
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
            time.sleep(0.02)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1.0, "decode_tok_s": 20.0,
                "tokens": 12, "plan_ms": 10.0}


def _tab_orch(tmp_path, *, server=None, engine=None, planner=None):
    server = server or FakeServer()
    orch = Orchestrator(
        server, Catalog.load(), Tracer(tmp_path / "traces"), engine=engine)
    orch.memory = WorkingMemory()
    orch.planner = planner
    return orch


def _skills(server):
    return [call for call in server.rpcs if call[0] == "skill"]


def test_wikipedia_followup_uses_current_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"navigate to wikipedia": ("open_url", 0.99)},
            argmap={("open_url", "navigate to wikipedia"): {
                "url": "https://en.wikipedia.org/"}})
        server = FakeServer()
        orch = Orchestrator(
            server, Catalog.load(), Tracer(tmp_path / "traces"),
            engine=engine)
        orch.memory = WorkingMemory()

        first = await orch.handle_utterance(
            "navigate to wikipedia", {"app": "Zen"})
        second = await orch.handle_utterance(
            "search for history",
            {"app": "Zen", "url": "https://en.wikipedia.org/"})

        assert first["outcome"] == "ok"
        assert second["outcome"] == "ok"
        assert engine.route_calls == ["navigate to wikipedia"]
        skills = _skills(server)
        assert [params["args"]["same_tab"] for _, params in skills] == [
            True, True]
        assert [params["args"]["browser"] for _, params in skills] == [
            "Zen", "Zen"]
        assert skills[-1][1]["args"]["url"] == (
            "https://en.wikipedia.org/w/index.php?search=history")

    run(go())


def test_new_tab_request_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open youtube in a new tab": ("open_url", 0.99)},
            argmap={("open_url", "open youtube in a new tab"): {
                "url": "https://youtube.com/"}})
        server = FakeServer()
        orch = _tab_orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open youtube in a new tab", {"app": "Zen"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    run(go())


def test_non_browser_frontmost_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open wikipedia": ("open_url", 0.99)},
            argmap={("open_url", "open wikipedia"): {
                "url": "https://en.wikipedia.org/"}})
        server = FakeServer()
        orch = _tab_orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open wikipedia", {"app": "Finder"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    run(go())


def test_requested_other_browser_does_not_set_same_tab(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"open wikipedia in safari": ("open_url", 0.99)},
            argmap={("open_url", "open wikipedia in safari"): {
                "url": "https://en.wikipedia.org/", "browser": "Safari"}})
        server = FakeServer()
        orch = _tab_orch(tmp_path, server=server, engine=engine)

        result = await orch.handle_utterance(
            "open wikipedia in safari", {"app": "Zen"})

        assert result["outcome"] == "ok"
        assert "same_tab" not in _skills(server)[0][1]["args"]

    run(go())


def test_web_search_only_reuses_search_engine_pages(tmp_path):
    async def route(url, path):
        engine = FakeEngine(
            routes={"search for history": ("web_search", 0.99)},
            argmap={("web_search", "search for history"): {
            "query": "history"}})
        server = FakeServer()
        orch = _tab_orch(tmp_path / path, server=server, engine=engine)
        orch.memory_enabled = False
        result = await orch.handle_utterance(
            "search for history", {"app": "Zen", "url": url})
        assert result["outcome"] == "ok"
        return _skills(server)[0][1]["args"]

    async def go():
        article = await route(
            "https://en.wikipedia.org/wiki/History", "article")
        google = await route(
            "https://www.google.com/search?q=a", "google")
        return article, google

    article_args, google_args = run(go())
    assert "same_tab" not in article_args
    assert google_args["same_tab"] is True
    assert google_args["browser"] == "Zen"


def test_page_task_uses_planner_and_planner_url_navigates_same_tab(tmp_path):
    async def go():
        engine = FakeEngine()
        server = FakeServer()
        planner = _HintPlanner([
            ['url "https://www.amazon.com/s?k=chicken"'],
            ['done "searched"'],
        ])
        orch = _tab_orch(
            tmp_path, server=server, engine=engine, planner=planner)

        result = await orch.handle_utterance(
            "add some chicken to my cart",
            {"app": "Google Chrome", "url": "https://www.amazon.com/"})

        assert result["outcome"] == "ok"
        assert engine.route_calls == []
        assert planner.calls[0]["hint"] and "amazon.com" in planner.calls[0]["hint"]
        skills = _skills(server)
        assert len(skills) == 1
        assert skills[0][1]["name"] == "open_url"
        assert skills[0][1]["args"]["same_tab"] is True
        assert skills[0][1]["args"]["browser"] == "Google Chrome"
        assert not any(method == "act" and params.get("op") == "url"
                       for method, params in server.rpcs)

    run(go())


def test_result_and_video_page_tasks_use_planner(tmp_path):
    async def run_case(utterance, url, name):
        engine = FakeEngine()
        planner = _HintPlanner([['done "done"']])
        orch = _tab_orch(tmp_path / name, engine=engine, planner=planner)
        result = await orch.handle_utterance(
            utterance, {"app": "Zen", "url": url})
        assert result["outcome"] == "ok"
        assert engine.route_calls == []
        assert len(planner.calls) == 1

    async def go():
        await run_case("click the first result",
                       "https://www.google.com/search?q=history", "google")
        await run_case("play the first video",
                       "https://www.youtube.com/results?search_query=history",
                       "youtube")

    run(go())


def test_page_task_for_different_site_uses_engine(tmp_path):
    async def go():
        engine = FakeEngine(
            routes={"add chicken to my walmart cart": ("web_search", 0.99)},
            argmap={("web_search", "add chicken to my walmart cart"): {
                "query": "chicken walmart"}})
        planner = _HintPlanner([['done "done"']])
        server = FakeServer()
        orch = _tab_orch(
            tmp_path, server=server, engine=engine, planner=planner)

        result = await orch.handle_utterance(
            "add chicken to my walmart cart",
            {"app": "Google Chrome", "url": "https://www.amazon.com/"})

        assert result["outcome"] == "ok"
        assert engine.route_calls == ["add chicken to my walmart cart"]
        assert planner.calls == []
        assert "same_tab" not in _skills(server)[0][1]["args"]

    run(go())


def test_compound_collection_disables_same_tab(tmp_path):
    orch = _tab_orch(tmp_path)
    orch._ctx["app"] = "Zen"
    orch._collect = []
    args = {"url": "https://en.wikipedia.org/"}
    result = orch._same_tab_args(
        "open_url", args, "open wikipedia", {"decisions": []})
    assert result is args
    assert "same_tab" not in result
