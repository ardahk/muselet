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


class FakeServer:
    def __init__(self, results=None):
        self.calls: list[tuple[str, dict]] = []
        self.timeouts: list[float] = []
        self.bubbles: list[str] = []
        self.says: list[str] = []
        self.moods: list[str] = []
        self.results = results or {}     # stage key -> result dict | Exception | callable

    @staticmethod
    def key(method, params):
        if method == "skill":
            return params["name"]
        code = params["code"]
        for k, marker in [("numbers_wait", "return POSIX path of"),
                          ("numbers_highlight", "background color"), ("numbers_review", "make new sheet"),
                          ("notes", "com.apple.Notes")]:
            if marker in code:
                return k
        return "?"

    async def rpc(self, method, params, timeout=30):
        self.calls.append((method, params))
        self.timeouts.append(timeout)
        k = self.key(method, params)
        r = self.results.get(k)
        if callable(r):
            r = await r()
        if isinstance(r, BaseException):
            raise r
        if r is not None:
            return r
        if k == "numbers_wait":
            return {"ok": True, "output": "/Users/x/Documents/Clients/Henderson/portfolio.xlsx"}
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


STEPS = ["open_app", "open_folder", "open_file", "numbers_wait", "numbers_highlight", "numbers_review", "notes"]
MEETING_BUBBLE = "Review Mon Oct 26, 10:00, per the client file."


def keys(orch):
    return [FakeServer.key(m, p) for m, p in orch.server.calls]


def test_happy_path_rpc_sequence_bubbles_and_outcome(clients):
    orch = FakeOrch()
    assert run(orch) == "ok"
    s = orch.server
    assert keys(orch) == STEPS
    assert s.calls[0] == ("skill", {"name": "open_app", "args": {"app": "Calendar"}})
    assert s.calls[1][1] == {"name": "open_folder", "args": {"path": str(clients / "Henderson")}}
    assert s.calls[2][1] == {"name": "open_file", "args": {"path": os.path.realpath(clients / "Henderson/portfolio.xlsx")}}
    assert all(m == "act" and p["op"] == "script" and p["lang"] == "applescript"
               for m, p in s.calls if m == "act")
    assert s.bubbles == [
        "Finding the client folder...",
        "Checking your calendar for the Hendersons...",
        MEETING_BUBBLE,
        "Opening the Hendersons' client folder...",
        "Reading the Hendersons' portfolio...",
        "Running the numbers on this Mac...",
        "Highlighting opportunities in Numbers...",
        "Writing the brief in Notes...",
    ]
    assert s.says == ["5 opportunities found. Brief is in Notes."]
    assert not any("$" in b for b in s.bubbles + s.says)
    assert all(len(b.split()) <= 12 for b in s.bubbles + s.says)
    assert s.moods[-1] == "success"
    d = next(d for d in orch.tracer.decisions if "prep" in d)
    assert d["meeting"]["start"] == "2026-10-26T10:00" and d["meeting"]["summary"] == "Henderson annual review"
    assert d["meeting_source"].endswith("Henderson/annual_review.ics") and "total_impact_usd" not in d
    assert d["normalized"] == "Henderson"
    assert d["document"] == os.path.realpath(clients / "Henderson/portfolio.xlsx")
    assert d["prep"]["tlh"]["evidence"]
    assert orch.tracer.decisions[-1] == {"tool": "advisor_prep", "skipped": []}
    assert "advisor_prep" in orch.tracer.stages and "advisor_prep.notes_brief" in orch.tracer.stages


def test_live_args_meeting_with_the_hendersons(clients):
    """Live E2E: the planner passed the whole phrase as the client."""
    orch = FakeOrch()
    assert run(orch, client="meeting with the hendersons") == "ok"
    assert orch.server.calls[1][1]["args"]["path"] == str(clients / "Henderson")


def test_every_step_has_a_5s_timeout(clients):
    orch = FakeOrch()
    assert run(orch) == "ok"
    assert tool.STEP_TIMEOUT_S == 5.0
    assert orch.server.timeouts == [5.0] * len(STEPS)


def test_calendar_is_never_scripted(clients):
    """Live E2E: `tell application id "com.apple.iCal"` blocked behind an Automation prompt."""
    orch = FakeOrch()
    assert run(orch) == "ok"
    assert not any("iCal" in p.get("code", "") or "Calendar" in p.get("code", "")
                   for m, p in orch.server.calls if m == "act")
    assert not hasattr(advisor, "calendar_lookup_script")
    assert "todays_agenda" not in keys(orch)


def test_meeting_time_comes_from_the_folder_ics(clients):
    ics = clients / "Henderson/annual_review.ics"
    ics.write_text(ics.read_text().replace("20261026T100000", "20261027T143000"))
    orch = FakeOrch()
    assert run(orch) == "ok"
    assert "Review Tue Oct 27, 14:30, per the client file." in orch.server.bubbles


def test_no_ics_still_runs(clients):
    (clients / "Henderson/annual_review.ics").unlink()
    orch = FakeOrch()
    assert run(orch) == "ok"
    assert "No meeting file for the Hendersons; continuing." in orch.server.bubbles


def test_golden_scripts_sent(clients):
    orch = FakeOrch()
    assert run(orch) == "ok"
    codes = {FakeServer.key(m, p): p["code"] for m, p in orch.server.calls if m == "act"}
    root = os.path.realpath(clients)
    for k in ("numbers_wait", "numbers_highlight", "numbers_review", "notes"):
        _golden(f"{k}.applescript", codes[k].replace(root, "<CLIENTS>"))
    prep = advisor.prep(advisor.load_household(HOUSEHOLD))
    xlsx = os.path.join(root, "Henderson", "portfolio.xlsx")
    assert codes["numbers_wait"] == advisor.numbers_wait_script(xlsx, tries=tool.NUMBERS_WAIT_TRIES)
    assert tool.NUMBERS_WAIT_TRIES * 0.1 < tool.STEP_TIMEOUT_S
    assert codes["numbers_highlight"] == advisor.numbers_highlight_script(prep, path=xlsx)
    assert codes["notes"].endswith('\tactivate\n\tshow n\nend tell\n')
    assert codes["notes"].replace("\tactivate\n\tshow n\n", "") == advisor.notes_brief_script(prep)


def test_scripts_target_the_opened_file_never_a_name_match(clients):
    """finance-22: every Numbers write resolves the document by the file path the tool opened."""
    orch = FakeOrch()
    assert run(orch) == "ok"
    codes = {FakeServer.key(m, p): p["code"] for m, p in orch.server.calls if m == "act"}
    xlsx = os.path.realpath(clients / "Henderson/portfolio.xlsx")
    for k in ("numbers_wait", "numbers_highlight", "numbers_review"):
        assert f'if POSIX path of ((file of d) as alias) is "{xlsx}" then set theDoc to contents of d' in codes[k]
        assert "front document" not in codes[k] and "starts with" not in codes[k]
        assert 'document "portfolio"' not in codes[k]
    assert "tell table 1 of sheet \"Holdings\" of theDoc" in codes["numbers_highlight"]
    assert "\ttell theDoc\n" in codes["numbers_review"]


def test_scripts_never_delete_user_content(clients):
    """finance-14: no Notes delete at all; a Review sheet is replaced only if it carries the Muselet marker."""
    orch = FakeOrch()
    assert run(orch) == "ok"
    codes = {FakeServer.key(m, p): p["code"] for m, p in orch.server.calls if m == "act"}
    assert "delete" not in codes["notes"]
    assert 'every note of f whose name is "Henderson — annual review prep (Muselet)"' in codes["notes"]
    assert "set body of n to" in codes["notes"]
    review = codes["numbers_review"]
    assert [ln.strip() for ln in review.splitlines() if ln.strip().startswith("delete")] == ["delete sheet nm"]
    assert review.index('if exists table "Muselet Allocation" of sheet nm then') < review.index("delete sheet nm")
    assert 'set nm to "Muselet Review"' in review and 'set nm to nm & " " & i' in review
    assert 'sheet "Review"' not in review


def test_final_bubble_counts_and_never_sums():
    """finance-16: the amounts are different kinds; the bubble gives the count only."""
    prep = advisor.prep(advisor.load_household(HOUSEHOLD))
    assert tool.final_bubble(prep) == "5 opportunities found. Brief is in Notes."
    assert tool.final_bubble({"opportunities": [{"impact_usd": "10.50"}]}) == "1 opportunity found. Brief is in Notes."
    assert tool.final_bubble({"opportunities": []}) == "No opportunities found. Brief is in Notes."
    assert not hasattr(tool, "total_impact")


def test_reads_run_concurrently_with_calendar(clients, monkeypatch):
    started = threading.Event()
    real = tool._load_prep

    def load(folder):
        started.set()
        return real(folder)

    async def calendar():
        for _ in range(200):          # Calendar RPC is still pending while prep runs in its thread
            if started.is_set():
                return {"ok": True}
            await asyncio.sleep(0.01)
        raise AssertionError("prep did not start while Calendar was opening")

    monkeypatch.setattr(tool, "_load_prep", load)
    assert run(FakeOrch({"open_app": calendar})) == "ok"


def test_unknown_client_fails_without_rpc(clients):
    orch = FakeOrch()
    assert run(orch, client="the Andersons") == "failed"
    assert orch.server.calls == []
    assert orch.server.says == ["No client folder for Anderson."]


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


@pytest.mark.parametrize("err", ["result", "raise", "rpc_timeout"])
def test_notes_failure_says_reason_and_fails(clients, err):
    r = {"result": {"ok": False, "error": "boom"}, "raise": RuntimeError("socket closed"),
         "rpc_timeout": RuntimeError("rpc act timed out")}[err]
    orch = FakeOrch({"notes": r})
    assert run(orch) == "failed"
    assert keys(orch) == STEPS
    assert orch.server.says == ["Couldn't write the brief in Notes."] and orch.server.moods[-1] == "confused"
    assert any("error" in d for d in orch.tracer.decisions)


OPTIONAL = [
    ("open_app", "Calendar didn't open in time; continuing.", "Calendar", STEPS[1:]),
    ("open_folder", "Finder didn't open in time; continuing.", "Finder", STEPS[2:]),
    ("open_file", "Numbers didn't open in time; continuing.", "Numbers", ["notes"]),
    ("numbers_wait", "Numbers didn't open the portfolio; continuing.", "Numbers", ["notes"]),
    ("numbers_highlight", "Couldn't highlight the sheet in time; continuing.", "Numbers", STEPS[5:]),
    ("numbers_review", "Couldn't add the Review sheet in time; continuing.", "Numbers", ["notes"]),
]


@pytest.mark.parametrize("stage,bubble,skipped,after", OPTIONAL)
@pytest.mark.parametrize("err", ["result", "rpc_timeout"])
def test_optional_step_failure_bubbles_and_continues(clients, stage, bubble, skipped, after, err):
    r = {"ok": False, "error": "boom"} if err == "result" else RuntimeError(f"rpc {stage} timed out")
    orch = FakeOrch({stage: r})
    assert run(orch) == "ok"
    k = keys(orch)
    assert k[k.index(stage) + 1:] == after
    assert bubble in orch.server.bubbles
    assert orch.server.says == [f"5 opportunities found. Brief in Notes; skipped {skipped}."]
    assert all(len(b.split()) <= 12 for b in orch.server.bubbles + orch.server.says)
    assert orch.tracer.decisions[-1] == {"tool": "advisor_prep", "skipped": [skipped]}


@pytest.mark.parametrize("stage,bubble,skipped,after", OPTIONAL[:3])
def test_hung_step_times_out_and_continues(clients, monkeypatch, stage, bubble, skipped, after):
    """The app never answers (e.g. a permission prompt): our own wait_for still ends the step."""
    monkeypatch.setattr(tool, "STEP_TIMEOUT_S", 0.05)

    async def hang():
        await asyncio.sleep(30)

    orch = FakeOrch({stage: hang})
    assert run(orch) == "ok"
    assert bubble in orch.server.bubbles
    assert orch.server.says[-1].endswith(f"skipped {skipped}.")


def test_hung_notes_times_out_and_fails(clients, monkeypatch):
    monkeypatch.setattr(tool, "STEP_TIMEOUT_S", 0.05)

    async def hang():
        await asyncio.sleep(30)

    orch = FakeOrch({"notes": hang})
    assert run(orch) == "failed"
    assert orch.server.says == ["Couldn't write the brief in Notes."]
    assert "timeout" in next(d["error"] for d in orch.tracer.decisions if "error" in d)


def test_several_skips_in_one_run(clients):
    orch = FakeOrch({"open_app": RuntimeError("rpc skill timed out"), "open_file": {"ok": False}})
    assert run(orch) == "ok"
    assert orch.server.says == ["5 opportunities found. Brief in Notes; skipped Calendar, Numbers."]


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
    ("meeting with the hendersons", "Henderson"),
    ("call with the Hendersons", "Henderson"),
    ("prep for the Hendersons", "Henderson"),
    ("review for the Henderson household", "Henderson"),
    ("the Henderson household", "Henderson"),
    ("the Henderson's", "Henderson"),
    ("prep me for my meeting with the Hendersons", "Henderson"),
    ("my annual review with the Hendersons", "Henderson"),
    ("meeting with Dr. Patel", "Patel"),
    ("call with the Garcias", "Garcia Household"),
    ("meeting with the Andersons", None),
    ("meeting with", None),
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


@pytest.mark.parametrize("raw,norm", [
    ("meeting with the hendersons", "henderson"),
    ("Meeting with the Hendersons.", "Henderson"),
    ("call with Hendersons", "Henderson"),
    ("prep for Henderson's", "Henderson"),
    ("review for the Henderson household", "Henderson"),
    ("the Henderson household", "Henderson"),
    ("the Hendersons", "Henderson"),
    ("Hendersons", "Henderson"),
    ("Henderson's", "Henderson"),
    ("the Hendersons\u2019", "Henderson"),
    ("the Hendersons' family", "Henderson"),
    ("prep me for my meeting with the Hendersons", "Henderson"),
    ("my annual review with the Hendersons", "Henderson"),
    ("the Joneses", "Jones"),
    ("the Bushes", "Bush"),
    ("the Rosses", "Ross"),
    ("the Garcias", "Garcia"),
    ("Mark and Elena Henderson", "Mark and Elena Henderson"),
    ("Henderson Trust", "Henderson Trust"),
    ("", ""),
])
def test_normalize_client(raw, norm):
    assert tool.normalize_client(raw) == norm


def test_singular_names_ending_in_s_still_match():
    """Plural stripping makes "Chris" -> "Chri"; the raw-token fallback still finds the folder."""
    names = ["Chris Davis", "Moses", "Henderson"]
    assert tool.match_client("Chris Davis", names)[0] == "Chris Davis"
    assert tool.match_client("meeting with the Moses", names)[0] == "Moses"
    assert tool.match_client("the Davises", names)[0] == "Chris Davis"


def test_final_bubble_with_skips():
    prep = {"opportunities": [{}] * 2}
    assert tool.final_bubble(prep, []) == "2 opportunities found. Brief is in Notes."
    assert tool.final_bubble(prep, ["Calendar", "Finder", "Numbers"]) == \
        "2 opportunities found. Brief in Notes; skipped Calendar, Finder, Numbers."
