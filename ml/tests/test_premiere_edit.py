import asyncio

import pytest

from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.tools import premiere_edit
from brain.traces import Tracer
from fakes import FakeServer


def make_orch(tmp_path, **kwargs):
    orch = Orchestrator(FakeServer(**kwargs), Catalog.load(),
                        Tracer(tmp_path / "traces"))
    orch._ctx = {"app": "Adobe Premiere Pro", "window_title": "Demo.prproj"}
    return orch


@pytest.mark.parametrize(("text", "expected"), [
    ("import the clips from my Desktop Footage folder",
     {"op": "import", "folder": "Footage"}),
    ("cut the clip at the playhead", {"op": "cut"}),
    ("add a cross dissolve", {"op": "transition"}),
    ("speed this up to 150%", {"op": "speed", "percent": 150}),
    ("add a marker here called intro", {"op": "marker", "name": "intro"}),
    ("export a 1080p H.264 to the Desktop", {"op": "export"}),
])
def test_parse_demo_requests(text, expected):
    assert premiere_edit.parse_request(
        text, {"app": "Adobe Premiere Pro 2026"}) == expected


def test_parse_request_context_exclusions_and_folder():
    assert premiere_edit.parse_request("export this", {"app": "Finder"}) is None
    for text in ("play", "stop the sequence", "go to start", "go to end", "undo"):
        assert premiere_edit.parse_request(
            text, {"app": "Adobe Premiere Pro"}) is None
    assert premiere_edit.parse_request(
        "import from the desktop B-roll folder",
        {"app": "Adobe Premiere Pro"}) == {
            "op": "import", "folder": "B-roll"}
    assert premiere_edit.parse_request(
        "speed this up", {"app": "Adobe Premiere Pro"}) is None
    assert premiere_edit.parse_request(
        "speed this up to double", {"app": "Adobe Premiere Pro"}) == {
            "op": "speed", "percent": 200}
    assert premiere_edit.parse_request(
        "speed this up to half", {"app": "Adobe Premiere Pro"}) == {
            "op": "speed", "percent": 50}


@pytest.mark.parametrize("text", [
    "add a marker called intro; later",
    "add a marker called intro/../../bad",
    "add a marker named " + "x" * 41,
])
def test_parse_marker_drops_invalid_name(text):
    assert premiere_edit.parse_request(
        text, {"app": "Adobe Premiere Pro"}) == {"op": "marker"}


@pytest.mark.parametrize(("op", "args", "summary"), [
    ("import", {"op": "import", "folder": "Footage"},
     "Premiere: import Footage?"),
    ("cut", {"op": "cut"}, "Premiere: cut at playhead?"),
    ("transition", {"op": "transition"}, "Premiere: add cross dissolve?"),
    ("speed", {"op": "speed", "percent": 150}, "Premiere: speed to 150%?"),
    ("marker", {"op": "marker", "name": "intro"},
     "Premiere: add marker intro?"),
    ("export", {"op": "export"}, "Premiere: export to Desktop?"),
])
def test_every_operation_confirms_before_any_rpc(
        tmp_path, monkeypatch, op, args, summary):
    monkeypatch.setenv("MUSELET_PREMIERE_CONFIRM", "each")
    orch = make_orch(tmp_path)
    orch.server.confirm_yes = False
    assert asyncio.run(premiere_edit.run(orch, args, "demo")) == "cancelled"
    assert orch.server.confirms == [summary]
    assert orch.server.rpcs == []


def test_confirm_timeout_is_cancelled_without_execution(tmp_path):
    orch = make_orch(tmp_path, confirm_raises=True)
    assert asyncio.run(premiere_edit.run(
        orch, {"op": "cut"}, "cut the clip")) == "cancelled"
    assert orch.server.rpcs == []


def test_project_confirmation_is_once_per_project_title(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSELET_PREMIERE_CONFIRM", "project")
    orch = make_orch(tmp_path)
    orch._ctx["window_title"] = "Muselet Demo run.prproj * - Adobe Premiere Pro"
    orch.server.handlers["act"] = lambda _params: {
        "ok": True, "output": "error:not_open"}

    async def scenario():
        first = await premiere_edit.run(orch, {"op": "cut"}, "cut")
        second = await premiere_edit.run(orch, {"op": "cut"}, "cut")
        orch._ctx["window_title"] = "Other.prproj - Adobe Premiere Pro"
        await premiere_edit._confirm(orch, {"op": "export"})
        return first, second

    assert asyncio.run(scenario()) == ("failed", "failed")
    assert orch.server.confirms == [
        "Let Muselet edit Muselet Demo run?",
        "Let Muselet edit Other?",
    ]


def test_both_existing_redirect_sites_dispatch_premiere_edit(tmp_path, monkeypatch):
    orch = make_orch(tmp_path)
    calls = []

    async def brain_tool(name, args, text):
        calls.append((name, args, text))
        return "ok"

    monkeypatch.setattr(orch, "_brain_tool", brain_tool)
    orch.engine = None
    orch.memory_enabled = False
    orch.route = lambda _text: {"kind": "answer"}
    first = asyncio.run(orch.handle_utterance(
        "cut the clip at the playhead", {"app": "Adobe Premiere Pro"}))
    assert first["outcome"] == "ok"
    assert calls[-1][:2] == ("premiere_edit", {"op": "cut"})

    trace = {"decisions": []}
    second = asyncio.run(orch._engine_route(
        "add a cross dissolve", trace))
    assert second == "ok"
    assert calls[-1][:2] == ("premiere_edit", {"op": "transition"})
    assert trace["decisions"] == [
        {"premiere_redirect": {"op": "transition"}}]


@pytest.mark.parametrize(("output", "message"), [
    ("error:missing", "Menu was missing"),
    ("error:disabled", "Menu was disabled"),
])
def test_menu_missing_and_disabled_are_reported(tmp_path, output, message):
    orch = make_orch(tmp_path)
    orch.server.handlers["act"] = lambda _params: {
        "ok": True, "output": output}
    with pytest.raises(premiere_edit.ToolError) as exc:
        asyncio.run(premiere_edit._click_menu(
            orch, ("Sequence", "Add Edit"),
            missing="Menu was missing", disabled="Menu was disabled"))
    assert exc.value.say == message


def test_undo_unchanged_fails_and_apple_script_strings_are_escaped(tmp_path):
    orch = make_orch(tmp_path)
    orch.server.handlers["act"] = lambda _params: {
        "ok": True, "output": "Undo Add Edit"}
    with pytest.raises(premiere_edit.ToolError, match="Undo Add Edit") as exc:
        asyncio.run(premiere_edit._verify_undo(orch, "Undo Add Edit"))
    assert exc.value.say == "Premiere didn't apply that"
    escaped = premiere_edit._as_str('clip "one" \\ safe')
    assert escaped == '"clip \\"one\\" \\\\ safe"'
    script = premiere_edit._menu_click(("File", "Import..."))
    assert 'name is "Import..." or name is "Import…"' in script


def test_import_empty_folder_fails_without_editing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        premiere_edit.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("MUSELET_PREMIERE_FOOTAGE", raising=False)
    (tmp_path / "Desktop" / "Footage").mkdir(parents=True)
    orch = make_orch(tmp_path)
    result = asyncio.run(premiere_edit.run(
        orch, {"op": "import", "folder": "Footage"}, "import clips"))
    assert result == "failed"
    assert orch.server.said == ["No clips in Desktop/Footage"]
    assert len(orch.server.rpcs) == 1
    assert orch.server.rpcs[0][1]["op"] == "script"


def test_missing_premiere_process_fails_before_editing(tmp_path):
    orch = make_orch(tmp_path)
    orch.server.handlers["act"] = lambda _params: {
        "ok": True, "output": "error:not_open"}
    result = asyncio.run(premiere_edit.run(
        orch, {"op": "cut"}, "cut at the playhead"))
    assert result == "failed"
    assert orch.server.said == ["Premiere Pro isn't open"]
    assert len(orch.server.rpcs) == 1


def test_export_poll_waits_for_stable_mp4_with_ftyp(tmp_path, monkeypatch):
    monkeypatch.setattr(
        premiere_edit.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MUSELET_PREMIERE_EXPORT_TIMEOUT", "0.05")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    exported = desktop / "Demo.mp4"
    exported.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 32)

    async def no_sleep(_duration):
        return None

    monkeypatch.setattr(premiere_edit.asyncio, "sleep", no_sleep)
    assert asyncio.run(premiere_edit._wait_export(None, {})) == exported


def test_export_poll_rejects_invalid_ftyp_and_times_out(
        tmp_path, monkeypatch):
    monkeypatch.setattr(
        premiere_edit.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("MUSELET_PREMIERE_EXPORT_TIMEOUT", "0.01")
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "broken.mp4").write_bytes(b"not an mp4 file")

    async def no_sleep(_duration):
        return None

    monkeypatch.setattr(premiere_edit.asyncio, "sleep", no_sleep)
    assert asyncio.run(premiere_edit._wait_export(None, {})) is None
