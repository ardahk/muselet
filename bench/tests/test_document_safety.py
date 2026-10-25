import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bench.harness.core import run_case
from bench.harness.documents import (
    DOCUMENT_APPS,
    DocumentInventoryError,
    close_created_script,
    created_items,
    document_apps_for_case,
    foreign_items,
    inventory_script,
    is_broad_close,
    may_edit_documents,
    quit_target,
    osascript_run_script,
    take_inventory,
    unclosable_items,
)


def _inventory_row(
    *,
    name="TextEdit",
    running=True,
    ax_windows=None,
    windows=None,
    documents=None,
):
    return {
        "name": name,
        "running": running,
        "ax_windows": list(ax_windows or []),
        "windows": list(windows or []),
        "documents": list(documents or []),
        "scripting_unavailable": False,
    }


class SafetyRuntime:
    def __init__(self, inventories=None, *, fail_script=None, predicate_output="ok"):
        self.calls = []
        self.inventories = list(inventories or [])
        self.fail_script = fail_script
        self.predicate_output = predicate_output
        self.first_action_monotonic = None
        self.terminal_monotonic = None
        self.utterance_monotonic = None
        self.utterance_wall = None
        self.trace_path = None

    async def start_scripts(self):
        self.calls.append(("start_scripts",))

    async def run_script(self, language, code, *, allow_inflight=False):
        self.calls.append(("script", language, code, allow_inflight))
        if code == self.fail_script:
            raise RuntimeError("script failure")
        if code.startswith("// muselet-doc-inventory"):
            if self.fail_script == "inventory":
                raise OSError("inventory unavailable")
            inventory = self.inventories.pop(0) if self.inventories else {}
            return {"output": json.dumps(inventory)}
        if code in ("false", "true", "no", "0"):
            return {"output": code}
        return {"output": self.predicate_output}

    async def start_utterance(self, utterance):
        self.calls.append(("utterance", utterance))
        self.utterance_monotonic = time.monotonic()
        self.utterance_wall = datetime.now(timezone.utc).isoformat()
        self.trace_path.write_text(
            json.dumps({
                "ts": self.utterance_wall,
                "utterance": utterance,
                "outcome": "ok",
            }) + "\n",
            encoding="utf-8",
        )

    async def prepare_for_cleanup(self):
        self.calls.append(("prepare_cleanup",))

    async def stop(self):
        self.calls.append(("stop",))

    def snapshot(self):
        return {
            "frames": [],
            "confirm_count": 0,
            "utterance_wall": self.utterance_wall,
        }

    def mark_utterance_finished(self):
        self.terminal_monotonic = time.monotonic()


def _all_apps_inventory(**overrides):
    inventory = {
        bundle_id: _inventory_row(name=app.name, running=False)
        for app in DOCUMENT_APPS
        for bundle_id in app.bundle_ids
    }
    for bundle_id, row in overrides.items():
        inventory[bundle_id] = row
    return inventory


async def _run_safety_case(case, runtime, trace_path):
    runtime.trace_path = trace_path
    return await run_case(
        case,
        runtime,
        values={},
        trace_path=trace_path,
        poll_interval=0.001,
    )


def test_false_and_raising_preconditions_skip_all_case_actions(tmp_path):
    async def scenario():
        for case, runtime, reason in (
            (
                {
                    "id": "false-precondition",
                    "utterance": "must not run",
                    "precondition": [{"shell": "false", "equals": "true"}],
                    "restore": [{"get": "get value", "set": "set value {value}"}],
                    "setup": [{"shell": "setup"}],
                    "teardown": [{"shell": "teardown"}],
                },
                SafetyRuntime(),
                "precondition failed",
            ),
            (
                {
                    "id": "raising-precondition",
                    "utterance": "must not run",
                    "precondition": [{"shell": "boom", "equals": "ok"}],
                    "restore": [{"get": "get value", "set": "set value {value}"}],
                    "setup": [{"shell": "setup"}],
                    "teardown": [{"shell": "teardown"}],
                },
                SafetyRuntime(fail_script="boom"),
                "precondition error",
            ),
        ):
            result = await _run_safety_case(case, runtime, tmp_path / f"{reason}.jsonl")
            assert result["status"] == "skipped"
            assert result["skip_reason"] == reason
            assert not any(call[0] in ("utterance", "prepare_cleanup") for call in runtime.calls)
            script_codes = [call[2] for call in runtime.calls if call[0] == "script"]
            assert script_codes in (["false"], ["boom"])
            assert runtime.calls[-1] == ("stop",)

    asyncio.run(scenario())


def test_trace_skill_precondition_is_skipped_as_nonmechanical(tmp_path):
    async def scenario():
        runtime = SafetyRuntime()
        result = await _run_safety_case(
            {
                "id": "trace-precondition",
                "utterance": "must not run",
                "precondition": [{"trace_skill": {"name": "create_note"}}],
                "restore": [{"get": "get value", "set": "set value {value}"}],
                "setup": [{"shell": "setup"}],
                "teardown": [{"shell": "teardown"}],
            },
            runtime,
            tmp_path / "trace-precondition.jsonl",
        )

        assert result["status"] == "skipped"
        assert result["skip_reason"] == "precondition not mechanical"
        assert runtime.calls == [("stop",)]

    asyncio.run(scenario())


def test_textedit_ax_window_skips_input_case_before_any_case_action(tmp_path):
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
        baseline = _all_apps_inventory(**{
            textedit.bundle_ids[0]: _inventory_row(
                ax_windows=["Untitled"],
                windows=[{"id": 11, "name": "Untitled"}],
            ),
        })
        runtime = SafetyRuntime([baseline])
        result = await _run_safety_case(
            {
                "id": "input-type",
                "category": "input",
                "utterance": "type see you at noon",
                "timeout_s": 0.001,
                "restore": [{"get": "restore get", "set": "restore set {value}"}],
                "setup": [{"shell": "setup"}],
                "teardown": [{"shell": "teardown"}],
            },
            runtime,
            tmp_path / "input-type.jsonl",
        )

        assert result["status"] == "skipped"
        assert result["skip_reason"] == "user_documents_open"
        assert result["user_documents"] == ["TextEdit AX window: Untitled", "TextEdit window: Untitled"]
        assert len([call for call in runtime.calls if call[0] == "script"]) == 1
        assert not any(call[0] == "utterance" for call in runtime.calls)
        assert runtime.calls[-1] == ("stop",)

    asyncio.run(scenario())


@pytest.mark.parametrize("running", [True, False])
def test_textedit_without_windows_or_documents_passes_document_guard(tmp_path, running):
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
        baseline = _all_apps_inventory(**{
            textedit.bundle_ids[0]: _inventory_row(running=running),
        })
        runtime = SafetyRuntime([baseline, baseline, baseline])
        result = await _run_safety_case(
            {
                "id": "input-type",
                "category": "input",
                "utterance": "type a short phrase",
            },
            runtime,
            tmp_path / f"textedit-{running}.jsonl",
        )

        assert result["status"] == "passed"
        assert result["document_baseline"][textedit.bundle_ids[0]]["running"] is running
        assert len([call for call in runtime.calls if call[0] == "utterance"]) == 1

    asyncio.run(scenario())


def test_inventory_failure_skips_case_as_unverifiable(tmp_path):
    async def scenario():
        runtime = SafetyRuntime(fail_script="inventory")
        result = await _run_safety_case(
            {"category": "input", "utterance": "type something"},
            runtime,
            tmp_path / "inventory-failure.jsonl",
        )

        assert result["status"] == "skipped"
        assert result["skip_reason"] == "user_documents_unverifiable"
        assert "inventory unavailable" in result["document_inventory_error"]
        assert not any(call[0] == "utterance" for call in runtime.calls)

    asyncio.run(scenario())


def test_typing_without_named_app_is_guarded_against_numbers_document(tmp_path):
    async def scenario():
        numbers = next(app for app in DOCUMENT_APPS if app.name == "Numbers")
        baseline = _all_apps_inventory(**{
            numbers.bundle_ids[0]: _inventory_row(
                name="Numbers",
                documents=[{"name": "Budget", "path": "/Users/test/Budget.numbers"}],
            ),
        })
        runtime = SafetyRuntime([baseline])
        result = await _run_safety_case(
            {"category": "system", "utterance": "type this into the document"},
            runtime,
            tmp_path / "typing-numbers.jsonl",
        )

        assert result["status"] == "skipped"
        assert result["skip_reason"] == "user_documents_open"
        assert "Numbers document: Budget" in result["user_documents"]
        assert len(result["document_apps"]) == len(DOCUMENT_APPS)

    asyncio.run(scenario())


def test_volume_case_is_not_guarded_by_open_textedit_document(tmp_path):
    async def scenario():
        runtime = SafetyRuntime()
        result = await _run_safety_case(
            {
                "id": "sys-vol-set",
                "category": "system",
                "utterance": "set the volume to thirty",
            },
            runtime,
            tmp_path / "volume.jsonl",
        )

        assert result["status"] == "passed"
        assert result["document_apps"] == []
        assert not any(
            call[0] == "script" and call[2].startswith("// muselet-doc-inventory")
            for call in runtime.calls
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("running", [True, False])
def test_document_app_quit_is_limited_to_apps_not_running_at_baseline(tmp_path, running):
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
        baseline = {textedit.bundle_ids[0]: _inventory_row(running=running)}
        runtime = SafetyRuntime([baseline, baseline, baseline])
        result = await _run_safety_case(
            {
                "document_apps": ["TextEdit"],
                "utterance": "do nothing",
                "teardown": [{
                    "applescript":
                        'if application "TextEdit" is running then tell application "TextEdit" to quit'
                }],
            },
            runtime,
            tmp_path / f"quit-{running}.jsonl",
        )

        quit_calls = [
            call for call in runtime.calls
            if call[0] == "script" and "to quit" in call[2]
        ]
        if running:
            assert not quit_calls
            assert result["teardown_observations"][-1]["skipped"] == (
                "document app was running at baseline"
            )
        else:
            assert len(quit_calls) == 1
            assert result["teardown_observations"][-1]["result"] == {"output": "ok"}

    asyncio.run(scenario())


def test_hobby_worker_document_skip_never_writes_task_to_worker(monkeypatch):
    from bench.hobbylm.replay import _run_hobby_worker_case
    from bench.hobbylm import replay

    monkeypatch.setattr(
        replay, "probe_session",
        lambda _binary: {"skip_reason": None, "session_probe": {"screen_locked": False}},
    )

    class FakeStdin:
        def __init__(self):
            self.writes = []

        def write(self, value):
            self.writes.append(value)

    class FakeProcess:
        def __init__(self):
            self.stdin = FakeStdin()

    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
        baseline = _all_apps_inventory(**{
            textedit.bundle_ids[0]: _inventory_row(
                ax_windows=["Untitled"],
                windows=[{"id": 11, "name": "Untitled"}],
            ),
        })

        async def run_script(_language, _code):
            return {"output": json.dumps(baseline)}

        process = FakeProcess()
        record = await _run_hobby_worker_case(
            process,
            helper=None,
            task={
                "id": "write-text",
                "kind": "input",
                "text": "write something in TextEdit",
                "expected": "done",
            },
            repeat=1,
            run_script=run_script,
        )

        assert record["status"] == "skipped"
        assert record["skip_reason"] == "user_documents_open"
        assert process.stdin.writes == []

    asyncio.run(scenario())


def test_hobby_worker_intercepts_finder_cleanup_by_case_created_ids():
    from bench.hobbylm.hobby_worker import run_task

    class FinderHelper:
        WORK = Path("/fake/hobby/data")
        CAL = type("Calendar", (), {"create_event": staticmethod(lambda *_args, **_kwargs: True)})()
        ids = {1}
        closed_ids = []

        @staticmethod
        def validate(proposal, *_args, **_kwargs):
            return "valid"

        @staticmethod
        def finder_window_ids():
            return sorted(FinderHelper.ids)

        @staticmethod
        def finder_windows():
            return len(FinderHelper.ids)

        @staticmethod
        def snapshot():
            return {"finder_windows": len(FinderHelper.ids)}

        @staticmethod
        def osa(script):
            return FinderHelper.sh("osascript", "-e", script)

        @staticmethod
        def sh(*args, **_kwargs):
            if args[0] == "open":
                FinderHelper.ids.add(2)
                return ""
            if len(args) >= 3 and "whose id is" in args[2]:
                identifier = int(args[2].split("whose id is", 1)[1].split(")", 1)[0])
                FinderHelper.ids.discard(identifier)
                FinderHelper.closed_ids.append(identifier)
                return ""
            return ""

    class Model:
        @staticmethod
        def complete(*_args, **_kwargs):
            return {}

    class MCP:
        @staticmethod
        def call(*_args, **_kwargs):
            return {}

    def trial(_model, _mcp, _item):
        FinderHelper.snapshot()
        FinderHelper.sh("open", "/Users/test/Downloads")
        FinderHelper.ids.add(3)
        FinderHelper.sh(str(FinderHelper.WORK / "brightness"), "set", "50")
        while FinderHelper.finder_windows() > 1:
            FinderHelper.osa(
                'tell application "Finder" to close front window'
            )
        return {"completed": True}

    FinderHelper.trial = staticmethod(trial)
    events = []
    row = run_task(
        FinderHelper,
        Model(),
        MCP(),
        ("folder-case", "folder", "open downloads", ""),
        events.append,
        lambda _timeout: True,
    )

    assert row["completed"] is True
    assert FinderHelper.closed_ids == [2]
    assert FinderHelper.ids == {1, 3}
    assert [event["ev"] for event in events] == ["setup_done", "pre_teardown", "done"]


def test_hobby_restore_closes_only_finder_ids_absent_from_baseline():
    from bench.hobbylm.replay import _restore

    class Helper:
        WORK = Path("/fake/hobby/data")
        calls = []

        @staticmethod
        def sh(*args):
            Helper.calls.append(("sh", args))
            return ""

        @staticmethod
        def osa(script):
            Helper.calls.append(("osa", script))
            return ""

        @staticmethod
        def finder_window_ids():
            return [1, 2, 3]

        @staticmethod
        def running(_app):
            return False

    before = {
        "bright": 0.5,
        "vol": (50, False),
        "dark": False,
        "finder_window_ids": [1, 2],
        "running": {},
    }
    _restore(Helper, before, {}, current={})

    close_scripts = [
        call[1] for call in Helper.calls
        if call[0] == "osa" and "close" in call[1]
    ]
    assert len(close_scripts) == 1
    assert "id is 3" in close_scripts[0]
    assert "front window" not in close_scripts[0]


def test_deskmind_document_skip_is_logged_without_task_run_directory(monkeypatch, tmp_path, capsys):
    from types import SimpleNamespace

    from bench.deskmind import run_muselet

    _guard_before_run = run_muselet._guard_before_run
    monkeypatch.setattr(
        run_muselet, "probe_session",
        lambda _binary: {"skip_reason": None, "session_probe": {"screen_locked": False}},
    )

    textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
    baseline = _all_apps_inventory(**{
        textedit.bundle_ids[0]: _inventory_row(
            ax_windows=["Untitled"],
            windows=[{"id": 24, "name": "Untitled"}],
        ),
    })

    async def run_script(_language, _script):
        return {"output": json.dumps(baseline)}

    task = SimpleNamespace(
        id="write-note",
        app="com.apple.TextEdit",
        reset_apps=[],
        stage=[],
        goal="write a note in TextEdit",
    )
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "muselet-write-note-1"

    result = _guard_before_run(
        task, 1, runs_dir, run_dir, run_script=run_script,
    )

    assert result is None
    assert not run_dir.exists()
    record = json.loads((runs_dir / "skipped.jsonl").read_text().strip())
    assert record["status"] == "skipped"
    assert record["skip_reason"] == "user_documents_open"
    assert "TextEdit AX window: Untitled" in record["user_documents"]
    assert json.loads(capsys.readouterr().out)["task_id"] == task.id


def test_deskmind_generic_window_cleanup_requires_captured_ids(monkeypatch, tmp_path):
    from bench.deskmind import run_muselet

    calls = []
    monkeypatch.setattr(run_muselet, "_app_running", lambda _name: True)
    monkeypatch.setattr(
        run_muselet.subprocess,
        "run",
        lambda command, **_kwargs: calls.append(command),
    )

    run_muselet._close_app_windows("com.microsoft.Excel", tmp_path)
    assert calls == []
    run_muselet._close_app_windows("com.microsoft.Excel", tmp_path, [17, 19])
    assert len(calls) == 1
    script = calls[0][-1]
    assert "id is 17" in script and "id is 19" in script
    assert "close front window" not in script


def test_live_suite_never_dispatches_broad_teardown_to_runtime(tmp_path):
    from bench.live.run_live import _load_suite
    from bench.harness.documents import is_document_close

    class LiveSuiteRuntime(SafetyRuntime):
        async def run_script(self, language, code, *, allow_inflight=False):
            if " is running" in code:
                self.calls.append(("script", language, code, allow_inflight))
                return {"output": "false"}
            return await super().run_script(
                language,
                code,
                allow_inflight=allow_inflight,
            )

        async def start_utterance(self, utterance):
            self.calls.append(("utterance", utterance))
            self.utterance_monotonic = time.monotonic()
            self.utterance_wall = datetime.now(timezone.utc).isoformat()
            self.trace_path.write_text(
                json.dumps({
                    "ts": self.utterance_wall,
                    "utterance": utterance,
                    "outcome": "ok",
                }) + "\n",
                encoding="utf-8",
            )

        def mark_utterance_finished(self):
            self.terminal_monotonic = time.monotonic()

        def snapshot(self):
            return {
                "frames": [],
                "confirm_count": 0,
                "utterance_wall": self.utterance_wall,
            }

    async def scenario():
        suite = Path(__file__).resolve().parents[2] / "evals/live_t1.jsonl"
        cases = _load_suite(suite)
        document_teardowns = [
            script
            for case in cases
            for step in case.get("teardown", [])
            for language in ("applescript", "shell", "jxa")
            if (script := step.get(language)) and is_document_close(str(script))
        ]
        assert document_teardowns
        assert {"app-open-textedit", "t2-textedit-write"} <= {
            case["id"] for case in cases
        }
        trace_path = tmp_path / "live-suite-traces.jsonl"
        for case in cases:
            runtime = LiveSuiteRuntime([
                _all_apps_inventory(),
                _all_apps_inventory(),
                _all_apps_inventory(),
            ])
            runtime.trace_path = trace_path
            await run_case(
                case,
                runtime,
                values={},
                trace_path=trace_path,
                poll_interval=0.001,
            )
            sent_scripts = [
                call[2] for call in runtime.calls
                if call[0] == "script"
            ]
            assert all(not is_document_close(script) for script in sent_scripts), case["id"]
            assert runtime.calls[-1] == ("stop",), case["id"]

    asyncio.run(scenario())

def test_document_apps_are_the_union_of_explicit_mentions_and_edit_heuristic():
    numbers = next(app for app in DOCUMENT_APPS if app.name == "Numbers")
    pages = next(app for app in DOCUMENT_APPS if app.name == "Pages")
    safari = next(app for app in DOCUMENT_APPS if app.name == "Safari")
    case = {
        "utterance": "open Safari",
        "document_apps": ["com.apple.iWork.Pages"],
        "teardown": [{"applescript": 'tell application id "com.apple.Numbers" to quit'}],
    }

    assert document_apps_for_case(case) == [pages, numbers, safari]
    assert document_apps_for_case({"category": "input", "utterance": "type hello"}) == list(
        DOCUMENT_APPS
    )
    assert may_edit_documents({"utterance": "please type hello"}) is True
    assert may_edit_documents({"category": "system", "utterance": "set the volume to thirty"}) is False


def test_case_classification_finds_app_alias_in_precondition_and_bundle_in_teardown():
    case = {
        "category": "system",
        "utterance": "check the screen brightness",
        "precondition": [{"applescript": 'application "Numbers Creator Studio" is running'}],
        "teardown": [{"applescript": 'tell application id "com.apple.Numbers" to quit'}],
    }

    assert document_apps_for_case(case) == [
        next(app for app in DOCUMENT_APPS if app.name == "Numbers")
    ]


def test_take_inventory_runs_one_marked_jxa_script_and_accepts_running_without_items():
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
        result = {
            textedit.bundle_ids[0]: _inventory_row(running=True),
        }
        calls = []

        async def run_script(language, code):
            calls.append((language, code))
            return {"output": json.dumps(result)}

        inventory = await take_inventory(run_script, [textedit])

        assert len(calls) == 1
        assert calls[0][0] == "jxa"
        assert calls[0][1].splitlines()[0] == "// muselet-doc-inventory"
        assert inventory == result
        assert foreign_items(inventory) == []

    asyncio.run(scenario())


def test_inventory_script_checks_running_before_touching_app_and_never_launches():
    textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")
    script = inventory_script([textedit])

    assert script.splitlines()[0] == "// muselet-doc-inventory"
    assert "activate" not in script.casefold()
    assert "launch" not in script.casefold()
    assert script.index("processes.whose") < script.index("Application(bundleId)")
    assert "if (processes.length > 0)" in script
    assert "processes[0].windows.name()" in script
    assert "window.id()" in script
    assert "document.path()" in script


def test_inventory_raises_for_run_script_error_or_unparseable_output():
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")

        async def failed_script(_language, _code):
            raise OSError("osascript unavailable")

        async def invalid_script(_language, _code):
            return {"output": "not json"}

        with pytest.raises(DocumentInventoryError, match="script failed"):
            await take_inventory(failed_script, [textedit])
        with pytest.raises(DocumentInventoryError, match="valid JSON"):
            await take_inventory(invalid_script, [textedit])

    asyncio.run(scenario())


def test_inventory_raises_when_system_events_cannot_read_running_app_windows():
    async def scenario():
        textedit = next(app for app in DOCUMENT_APPS if app.name == "TextEdit")

        async def run_script(_language, _code):
            return {"output": json.dumps({
                textedit.bundle_ids[0]: {
                    **_inventory_row(running=True),
                    "system_events_error": "not authorized",
                },
            })}

        with pytest.raises(DocumentInventoryError, match="could not read windows"):
            await take_inventory(run_script, [textedit])

    asyncio.run(scenario())


def test_osascript_adapter_uses_jxa_and_kills_timed_out_process(monkeypatch):
    async def scenario():
        calls = []

        class Process:
            returncode = 0

            async def communicate(self):
                return b"{}", b""

            async def wait(self):
                calls.append(("wait",))

            def kill(self):
                calls.append(("kill",))

        async def create_subprocess_exec(*args, **kwargs):
            calls.append((args, kwargs))
            return Process()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess_exec)
        result = await osascript_run_script("jxa", "JSON.stringify({})")
        assert result == {"output": "{}", "stderr": "", "returncode": 0}
        assert calls[0][0] == (
            "osascript", "-l", "JavaScript", "-e", "JSON.stringify({})"
        )

        class HangingProcess(Process):
            async def communicate(self):
                await asyncio.sleep(1)
                return b"", b""

        async def create_hanging_process(*_args, **_kwargs):
            return HangingProcess()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_hanging_process)
        with pytest.raises(DocumentInventoryError, match="timed out after 0.001s"):
            await osascript_run_script("jxa", "hang", timeout=0.001)
        assert calls[-2:] == [("kill",), ("wait",)]

    asyncio.run(scenario())


def test_foreign_items_includes_accessibility_windows_scripted_windows_and_documents():
    baseline = {
        "com.apple.TextEdit": _inventory_row(
            ax_windows=["Document 1"],
            windows=[{"id": 4, "name": "Document 1"}],
            documents=[{"name": "Document 1", "path": "/Users/test/Document 1.rtf"}],
        ),
        "com.apple.Pages": {
            **_inventory_row(name="Pages", running=False),
            "ax_windows": ["ignored while not running"],
        },
    }

    assert foreign_items(baseline) == [
        "TextEdit AX window: Document 1",
        "TextEdit window: Document 1",
        "TextEdit document: Document 1",
    ]


def test_created_items_and_close_script_only_target_new_window_ids_and_document_paths():
    app_id = "com.apple.TextEdit"
    baseline = {app_id: _inventory_row()}
    after_setup = {
        app_id: _inventory_row(
            windows=[{"id": 11, "name": "Untitled"}],
            documents=[{"name": "Untitled", "path": "/case/one.rtf"}],
        ),
    }
    pre_teardown = {
        app_id: _inventory_row(
            windows=[
                {"id": 11, "name": "Untitled"},
                {"id": 12, "name": "Untitled 2"},
            ],
            documents=[
                {"name": "Untitled", "path": "/case/one.rtf"},
                {"name": "Untitled 2", "path": "/case/two.rtf"},
            ],
        ),
    }

    created = created_items(baseline, after_setup, pre_teardown)
    script = close_created_script(created)

    assert created[app_id]["windows"] == [
        {"id": 11, "name": "Untitled"},
        {"id": 12, "name": "Untitled 2"},
    ]
    assert created[app_id]["documents"] == [
        {"name": "Untitled", "path": "/case/one.rtf"},
        {"name": "Untitled 2", "path": "/case/two.rtf"},
    ]
    assert "11" in script and "12" in script
    assert "Untitled" in script and "Untitled 2" in script
    assert "one.rtf" in script and "two.rtf" in script
    assert 'app.windows.byId(windowInfo.id).close({saving: "no"})' in script
    assert is_broad_close(script) is False


@pytest.mark.parametrize(
    "script",
    [
        'tell application "TextEdit" to close every document saving no',
        'tell application "TextEdit" to close (every document saving no)',
        'tell application "TextEdit" to close every window',
        'tell application "TextEdit" to close (every window)',
        'tell application "TextEdit" to close documents',
        'tell application "TextEdit" to close windows',
        'tell application "TextEdit" to close front window',
        'Application("TextEdit").documents().forEach(document => document.close())',
        'Application("TextEdit").windows().forEach(window => window.close())',
    ],
)
def test_broad_close_detector_rejects_unfiltered_collection_closes(script):
    assert is_broad_close(script) is True


@pytest.mark.parametrize(
    "script",
    [
        'tell application "TextEdit" to close (every document whose path is "/tmp/a") saving no',
        'tell application "Safari" to close (every document whose URL contains "example.com")',
        'tell application "TextEdit" to close (every window whose id is 11)',
        'tell application "TextEdit" to close (every document whose name is "Untitled") saving no',
        'Application("TextEdit").documents.whose({name: "Untitled"}).forEach(d => d.close())',
    ],
)
def test_broad_close_detector_allows_explicitly_filtered_closes(script):
    assert is_broad_close(script) is False


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ('if application "TextEdit" is running then tell application "TextEdit" to quit', "TextEdit"),
        ('tell application id "com.apple.Numbers" to quit', "Numbers"),
        ('quit app "Adobe Premiere Pro 2026"', "Adobe Premiere Pro"),
        ('tell application "Calculator" to quit', None),
    ],
)
def test_quit_target_only_identifies_known_document_apps(script, expected):
    target = quit_target(script)
    assert (target.name if target else None) == expected


def test_close_script_returns_none_when_no_created_item_can_be_targeted():
    created = {
        "com.apple.TextEdit": {
            "windows": [{"name": "Untitled"}],
            "documents": [{"name": "Untitled"}],
            "unidentified": [],
        },
    }
    assert close_created_script(created) is None


def test_tracked_created_window_close_suppresses_save_sheet():
    created = {
        "com.apple.TextEdit": {
            "windows": [{"id": 11, "name": "Untitled"}],
            "documents": [],
            "unidentified": [],
        },
    }

    script = close_created_script(created)

    assert 'app.windows.byId(windowInfo.id).close({saving: "no"})' in script


def test_pathless_created_document_is_closable_through_its_created_window():
    app_id = "com.apple.TextEdit"
    baseline = {app_id: _inventory_row(running=False)}
    with_window = {
        app_id: _inventory_row(
            windows=[{"id": 11, "name": "Untitled"}],
            documents=[{"name": "Untitled", "path": None}],
        ),
    }

    created_with_window = created_items(baseline, with_window)
    close_script = close_created_script(created_with_window)

    assert close_script is not None
    assert "11" in close_script
    assert not unclosable_items(created_with_window)

    without_window = {
        app_id: _inventory_row(
            documents=[{"name": "Untitled", "path": None}],
        ),
    }
    created_without_window = created_items(baseline, without_window)
    assert any(
        item["bundle_id"] == app_id and item["type"] == "document"
        for item in unclosable_items(created_without_window)
    )


def test_filtered_case_document_close_is_delegated_to_tracked_cleanup(tmp_path):
    async def scenario():
        close_step = {
            "applescript": (
                'tell application "TextEdit" to close '
                '(every document whose name is "Untitled") saving no'
            ),
        }
        runtime = SafetyRuntime([
            _all_apps_inventory(),
            _all_apps_inventory(),
            _all_apps_inventory(),
        ])
        result = await _run_safety_case(
            {
                "id": "filtered-document-close",
                "category": "system",
                "utterance": "set volume to thirty",
                "timeout_s": 0.001,
                "teardown": [close_step],
            },
            runtime,
            tmp_path / "filtered-document-close.jsonl",
        )

        assert close_step not in [
            call[2] for call in runtime.calls if call[0] == "script"
        ]
        assert any(
            observation.get("step") == close_step
            and observation.get("skipped")
            == "case close delegated to tracked cleanup"
            for observation in result["teardown_observations"]
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ('tell application "TextEdit" to close document 1', True),
        ('tell application "TextEdit" to close (every document whose name is "Untitled")', True),
        ('tell application "TextEdit" to close front window', True),
        ('tell application "TextEdit" to close every window', True),
        (
            'Application("TextEdit").documents.whose({name: "Untitled"})()'
            '.forEach(document => document.close())',
            True,
        ),
        ('Application("TextEdit").windows.byId(11).close()', True),
        ('tell application "TextEdit" to quit', False),
        ('tell application "System Events" to set volume output volume 50', False),
        ('tell application "System Events" to close access fileRef', False),
        ('exec 3>&-', False),
    ],
)
def test_document_close_detector_classifies_document_and_window_targets(script, expected):
    from bench.harness import documents

    detector = getattr(documents, "is_document_close", None)
    assert callable(detector)
    assert detector(script) is expected


def test_chat_mail_and_browser_apps_are_inventoried_through_system_events_only():
    unscripted = {app.name for app in DOCUMENT_APPS if not app.scripted}
    assert {"Mail", "Messages", "Slack", "Safari", "Google Chrome", "Reminders"} <= unscripted
    assert {"TextEdit", "Numbers", "Pages", "Notes"}.isdisjoint(unscripted)
    script = inventory_script(DOCUMENT_APPS)
    assert '"scripted": false' in script and "if (!appInfo.scripted)" in script
    skip = script.index("if (!appInfo.scripted)")
    assert script.index("processes[0].windows.name()") < skip < script.index("Application(bundleId)")
