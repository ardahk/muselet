import asyncio

import pytest

from brain.orchestrator import Orchestrator
from brain.sites import APP_SCHEMES, fix_url
from fakes import FakeServer


INSTALLED = ["Slack", "zoom.us", "Microsoft Teams", "Microsoft Outlook"]


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
