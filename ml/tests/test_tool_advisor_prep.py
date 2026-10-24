"""brain.tools.advisor_prep with a fake orch: RPC sequence, golden scripts, bubbles, outcomes, client matching.

Run: PYTHONPATH=ml/src python -m pytest ml/tests/test_tool_advisor_prep.py
Regenerate goldens: UPDATE_GOLDEN=1 PYTHONPATH=ml/src python -m pytest ml/tests/test_tool_advisor_prep.py
"""

import asyncio
import os
import shutil
import threading
from pathlib import Path

import pytest
from brain import advisor
from brain.tools import advisor_prep as tool

ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLD = ROOT / "evals/fixtures/advisor/henderson"
GOLDEN = Path(__file__).resolve().parent / "golden/advisor_prep"
CAL_OK = "Henderson annual review\n2026-10-26T10:00:00\n2026-10-26T11:00:00"


class FakeServer:
    def __init__(self, results=None):
        self.calls: list[tuple[str, dict]] = []
        self.bubbles: list[str] = []
        self.says: list[str] = []
        self.moods: list[str] = []
        self.results = results or {}     # stage key -> result dict | Exception | callable

    @staticmethod
    def key(method, params):
        if method == "skill":
            return params["name"]
        code = params["code"]
        for k, marker in [("calendar", "com.apple.iCal"), ("numbers_wait", "starts with"),
                          ("numbers_highlight", "background color"), ("numbers_review", "make new sheet"),
                          ("notes", "com.apple.Notes")]:
            if marker in code:
                return k
        return "?"

    async def rpc(self, method, params, timeout=30):
        self.calls.append((method, params))
        k = self.key(method, params)
        r = self.results.get(k)
        if callable(r):
            r = await r()
        if isinstance(r, BaseException):
            raise r
        if r is not None:
            return r
        if k == "calendar":
            return {"ok": True, "output": CAL_OK}
        if k == "numbers_wait":
            return {"ok": True, "output": "portfolio"}
        return {"ok": True}

    async def say(self, text):
        self.says.append(text)

    async def ui(self, mood, bubble=None):
        self.moods.append(mood)
        if bubble:
            self.bubbles.append(bubble)


class FakeTracer:
    def __init__(self):
        self.stages, self.rpcs, self.decisions = {}, [], []

    def stage(self, name, ms):
        self.stages[name] = ms

    def rpc(self, method, params, result, ms):
        self.rpcs.append(method)

    def decision(self, info):
        self.decisions.append(info)


class FakeOrch:
    def __init__(self, results=None):
        self.server = FakeServer(results)
        self.tracer = FakeTracer()


@pytest.fixture
def clients(tmp_path, monkeypatch):
    root = tmp_path / "Clients"
    shutil.copytree(HOUSEHOLD, root / "Henderson")
    (root / "Garcia Household").mkdir()
    (root / ".DS_Store").write_text("")
    monkeypatch.setenv("MUSELET_CLIENTS_DIR", str(root))
    monkeypatch.setattr(tool, "PAUSE_S", 0)
    return root


def run(orch, client="the Hendersons", utterance="prep me for my meeting with the Hendersons"):
    return asyncio.run(tool.run(orch, {"client": client}, utterance))


def _golden(name, text):
    path = GOLDEN / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    assert text == path.read_text()


def test_happy_path_rpc_sequence_bubbles_and_outcome(clients):
    orch = FakeOrch()
    assert run(orch) == "ok"
    s = orch.server
    assert [FakeServer.key(m, p) for m, p in s.calls] == [
        "calendar", "open_folder", "open_file", "numbers_wait", "numbers_highlight", "numbers_review", "notes"]
    assert s.calls[1][1] == {"name": "open_folder", "args": {"path": str(clients / "Henderson")}}
    assert s.calls[2][1] == {"name": "open_file", "args": {"path": str(clients / "Henderson/portfolio.xlsx")}}
    assert all(m == "act" and p["op"] == "script" and p["lang"] == "applescript"
               for m, p in s.calls if m == "act")
    assert s.bubbles == [
        "Finding the client folder...",
        "Checking your calendar for the Hendersons...",
        "Opening the Hendersons' client folder...",
        "Reading the Hendersons' portfolio...",
        "Running the numbers on this Mac...",
        "Highlighting opportunities in Numbers...",
        "Writing the brief in Notes...",
    ]
    assert s.says == ["Brief in Notes: 5 opportunities, $332,329 total impact."]
    assert all(len(b.split()) <= 12 for b in s.bubbles + s.says)
    assert s.moods[-1] == "success"
    d = orch.tracer.decisions[-1]
    assert d["total_impact_usd"] == "332328.60" and d["calendar"]["start"] == "2026-10-26T10:00"
    assert d["prep"]["tlh"]["evidence"]
    assert "advisor_prep" in orch.tracer.stages and "advisor_prep.notes_brief" in orch.tracer.stages


def test_golden_scripts_sent(clients):
    orch = FakeOrch()
    assert run(orch) == "ok"
    codes = {FakeServer.key(m, p): p["code"] for m, p in orch.server.calls if m == "act"}
    for k in ("calendar", "numbers_wait", "numbers_highlight", "numbers_review", "notes"):
        _golden(f"{k}.applescript", codes[k])
    prep = advisor.prep(advisor.load_household(HOUSEHOLD))
    assert codes["numbers_highlight"] == advisor.numbers_highlight_script(prep, document="portfolio")
    assert codes["notes"].endswith('\tactivate\n\tshow n\nend tell\n')
    assert codes["notes"].replace("set n to make", "make").replace("\tactivate\n\tshow n\n", "") == \
        advisor.notes_brief_script(prep)


def test_final_bubble_is_deterministic_sum():
    prep = advisor.prep(advisor.load_household(HOUSEHOLD))
    assert str(tool.total_impact(prep)) == "332328.60"
    assert tool.final_bubble(prep) == "Brief in Notes: 5 opportunities, $332,329 total impact."
    assert tool.final_bubble({"opportunities": [{"impact_usd": "10.50"}]}) == \
        "Brief in Notes: 1 opportunity, $11 total impact."


def test_reads_run_concurrently_with_calendar(clients, monkeypatch):
    started = threading.Event()
    real = tool._load_prep

    def load(folder):
        started.set()
        return real(folder)

    async def calendar():
        for _ in range(200):          # calendar RPC is still pending while prep runs in its thread
            if started.is_set():
                return {"ok": True, "output": CAL_OK}
            await asyncio.sleep(0.01)
        raise AssertionError("prep did not start while Calendar was being read")

    monkeypatch.setattr(tool, "_load_prep", load)
    assert run(FakeOrch({"calendar": calendar})) == "ok"


def test_unknown_client_fails_without_rpc(clients):
    orch = FakeOrch()
    assert run(orch, client="the Andersons") == "failed"
    assert orch.server.calls == []
    assert orch.server.says == ["No client folder for the Andersons."]


def test_ambiguous_client_fails(clients):
    shutil.copytree(clients / "Henderson", clients / "Henderson Trust")
    (clients / "Henderson").rename(clients / "Henderson Estate")
    orch = FakeOrch()
    assert run(orch, client="Henderson") == "failed"
    assert orch.server.says == ["Two client folders match Henderson; which one?"]


def test_missing_files_fail(clients):
    (clients / "Henderson/portfolio.xlsx").unlink()
    orch = FakeOrch()
    assert run(orch) == "failed"
    assert orch.server.says == ["Couldn't find the Hendersons' portfolio files."] and orch.server.calls == []


@pytest.mark.parametrize("stage,say", [
    ("open_folder", "Couldn't open the Hendersons' folder."),
    ("open_file", "Couldn't open the Hendersons' portfolio."),
    ("numbers_wait", "Numbers didn't open the portfolio."),
    ("numbers_highlight", "Couldn't highlight the portfolio sheet."),
    ("numbers_review", "Couldn't add the Review sheet."),
    ("notes", "Couldn't write the brief in Notes."),
])
@pytest.mark.parametrize("err", ["result", "raise"])
def test_rpc_failure_says_reason_and_stops(clients, stage, say, err):
    r = {"ok": False, "error": "boom"} if err == "result" else RuntimeError("rpc act timed out")
    orch = FakeOrch({stage: r})
    assert run(orch) == "failed"
    keys = [FakeServer.key(m, p) for m, p in orch.server.calls]
    assert keys[-1] == stage
    assert orch.server.says == [say] and orch.server.moods[-1] == "confused"
    assert any("error" in d for d in orch.tracer.decisions)


@pytest.mark.parametrize("cal,bubble", [
    ({"ok": True, "output": ""}, "No Henderson meeting on the calendar this month."),
    (RuntimeError("rpc act timed out"), "Calendar didn't answer; using the client folder."),
])
def test_calendar_miss_is_not_fatal(clients, cal, bubble):
    orch = FakeOrch({"calendar": cal})
    assert run(orch) == "ok"
    assert bubble in orch.server.bubbles


def test_bad_portfolio_fails_cleanly(clients):
    p = clients / "Henderson/portfolio.csv"
    p.write_text(p.read_text().replace("US equity", "Crypto", 1))
    orch = FakeOrch()
    assert run(orch) == "failed"
    assert orch.server.says == ["Couldn't read the Hendersons' files."]
    assert "numbers_highlight" not in [FakeServer.key(m, p) for m, p in orch.server.calls]


def test_cancel_propagates(clients):
    async def stop():
        raise asyncio.CancelledError

    orch = FakeOrch({"open_file": stop})
    with pytest.raises(asyncio.CancelledError):
        run(orch)
    assert orch.server.says == []


def test_cancel_from_outside_mid_rpc(clients):
    async def main():
        hang = asyncio.Event()

        async def block():
            await hang.wait()

        orch = FakeOrch({"open_folder": block})
        task = asyncio.create_task(tool.run(orch, {"client": "Hendersons"}, ""))
        while len(orch.server.calls) < 2:
            await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return orch

    orch = asyncio.run(main())
    assert orch.server.says == []


@pytest.mark.parametrize("client,expected", [
    ("the Hendersons", "Henderson"),
    ("Hendersons", "Henderson"),
    ("Henderson household", "Henderson"),
    ("henderson", "Henderson"),
    ("the Henderson family", "Henderson"),
    ("Henderson's", "Henderson"),
    ("the Hendersons\u2019", "Henderson"),
    ("Mark and Elena Henderson", "Henderson"),
    ("the Hendersens", "Henderson"),
    ("HENDERSON", "Henderson"),
    ("the Garcias", "Garcia Household"),
    ("Garcia household", "Garcia Household"),
    ("the Andersons", None),
    ("the Smiths", None),
    ("my clients", None),
    ("", None),
])
def test_match_client(client, expected):
    assert tool.match_client(client, ["Garcia Household", "Henderson", "Patel"])[0] == expected


def test_match_prefers_exact_folder_over_extra_words():
    assert tool.match_client("the Hendersons", ["Henderson", "Henderson Trust"])[0] == "Henderson"
    assert tool.match_client("Henderson trust", ["Henderson", "Henderson Trust"])[0] == "Henderson Trust"


def test_display_name():
    assert tool.display_name(Path("Henderson")) == "the Hendersons"
    assert tool.display_name(Path("Garcia Household")) == "the Garcias"
    assert tool.display_name(Path("Ross")) == "the Rosses"
