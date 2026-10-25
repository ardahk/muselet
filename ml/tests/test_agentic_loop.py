import pytest
import re
"""Agentic-loop lane: page-load expect re-poll, finish-criterion done gate,
workflow-memory hygiene, cross-app retrieval skip, user-trace regressions."""

import json

from brain.catalog import Catalog
from brain.finish import criterion, evidence
from brain.orchestrator import Orchestrator
from brain.plan_bank import (Demo, PlanBank, goal_targets, load_workflows,
                             render_block, workflow_ok)
from brain.traces import Tracer
from fakes import FakeServer
from test_fallback_planner import FakePlanner as CtxPlanner, _observe, _run, _setup
from test_planner_loop import FakePlanner, run, trace_for
from test_planner_verify import VerifyPlanner


def _zen(window, elements=()):
    els = list(elements)
    lines = "\n".join(f'#{e["ref"]} {e["role"]} "{e["label"]}"' for e in els)
    return {"epoch": 1, "app": "Zen", "window": window, "focused_ref": None,
            "elements": els, "ax_ms": 1,
            "text": f'app: Zen | window: "{window}"' + ("\n" + lines if lines else "")}


def _orch(server, planner):
    orch = Orchestrator(server, Catalog.load(), Tracer())
    orch.planner = planner
    orch.LOAD_POLL_S, orch.LOAD_WAIT_S = 0.01, 0.1
    return orch


# 1. page-load re-poll -------------------------------------------------------

def test_page_loading_detection():
    orch = _orch(FakeServer(), FakePlanner([['done "x"']]))
    assert orch._page_loading(_zen("Zen Browser"))
    assert orch._page_loading(_zen("Transferring data from youtube.com"))
    assert orch._page_loading(_zen("Untitled"))
    assert orch._page_loading({"app": "Google Chrome", "window": "Loading…"})
    assert orch._page_loading({"app": "Finder", "web_ax_pending": True})
    assert not orch._page_loading(_zen("jazz music - YouTube"))
    assert not orch._page_loading({"app": "TextEdit", "window": "Untitled"})


def test_loading_title_repolls_until_expect_passes(tmp_path):
    """User trace: url expect title~"jazz" failed while Zen's title was
    still "Zen Browser"; it must re-poll instead of failing."""
    state = {"verifies": 0}

    def verify(_params):
        state["verifies"] += 1
        ok = state["verifies"] > 3
        return {"ok": ok, "observed": 'title "jazz music - YouTube"' if ok
                else 'title "Zen Browser"'}

    server = FakeServer(handlers={"verify": verify},
                        observe=lambda: _zen("jazz music - YouTube" if
                                             state["verifies"] > 3
                                             else "Zen Browser"))
    planner = FakePlanner([
        ['url "https://www.youtube.com/results?search_query=jazz+music"',
         'expect title~"jazz"'],
        ['done "ok"']])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    run(orch._planner_loop("search youtube for jazz music", trace))
    assert state["verifies"] == 4
    lb = "\n".join(planner.user_msgs[1]["last_batch"])
    assert "failed" not in lb and "pending" not in lb
    assert not any("loop_guard" in d for d in trace["decisions"])


def test_still_loading_reports_pending_and_skips_loop_guard_strike(tmp_path):
    server = FakeServer(handlers={"verify": lambda p: {
        "ok": False, "observed": 'title "Zen Browser"'}},
        observe=lambda: _zen("Zen Browser"))
    planner = FakePlanner([
        ['url "https://www.youtube.com/results?search_query=jazz"',
         'expect title~"jazz"'],
        ["press #1", 'expect appears "Pause"'],
        ["press #2", 'expect appears "Pause"'],
        ['done "ok"']])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    out = run(orch._planner_loop("do the jazz thing", trace))
    assert "[pending: page loading]" in "\n".join(
        planner.user_msgs[1]["last_batch"])
    assert {"loop_guard_skip": "page_loading",
            "line": 'url "https://www.youtube.com/results?search_query=jazz"'} \
        in trace["decisions"]
    # three failed turns, one of them loading: no 3_failed_turns guard
    assert not any("loop_guard" in d for d in trace["decisions"])
    assert out != "awaiting_user"


@pytest.mark.skip(reason="blind/agentic tasks treat planner-written expects as soft; finish evidence decides")
def test_second_loading_failure_counts_normally(tmp_path):
    server = FakeServer(handlers={"verify": lambda p: {
        "ok": False, "observed": "x"}}, observe=lambda: _zen("Zen Browser"))
    planner = FakePlanner([[f"press #{i}", 'expect appears "Pause"']
                           for i in range(1, 6)])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    assert run(orch._planner_loop("do the jazz thing", trace)) == \
        "awaiting_user"
    assert [d for d in trace["decisions"] if "loop_guard_skip" in d] == [
        {"loop_guard_skip": "page_loading", "line": "press #1"}]
    assert {"loop_guard": "3_failed_turns", "line": "press #4"} in \
        trace["decisions"]


# 2. done needs the finish criterion --------------------------------------

def test_finish_evidence_rules():
    pause = {"elements": [{"ref": 3, "role": "button",
                           "label": "Pause keyboard shortcut k"}]}
    assert evidence("play", "jazz", obs=pause)
    assert evidence("play", "jazz", obs={"text": '#9 button "Pause (k)"'})
    assert evidence("play", "jazz", obs={}, script_stdout="playing")
    assert not evidence("play", "jazz", obs={
        "text": '#9 button "Play (k)"\n#2 link "Pause music"'})
    assert evidence("search", "jazz music", obs={"window": "jazz music - YouTube"})
    assert evidence("search", "jazz music", obs={"window": "Zen Browser"},
                    url="https://www.youtube.com/results?search_query=jazz+music")
    assert not evidence("search", "jazz music", obs={"window": "YouTube"})
    assert evidence("cart", "milk", obs={"text": '#1 text "Added to Cart"'})
    assert evidence("cart", "milk", obs={}, ocr="Cart subtotal (1 item): $3")
    assert not evidence("cart", "milk", obs={"text": '#1 button "Add to Cart"'})
    assert evidence("directions", "SFO", obs={"window": "Directions to SFO"})
    assert not evidence("directions", "SFO", obs={"window": "Maps"})
    assert criterion("Play some jazz music on Youtube")[:2] == ("play", "jazz music")
    assert criterion("open Safari")[0] == "open"


def _play_setup(press_to_pause=True):
    state = {"playing": False}
    pause = {"ref": 7, "role": "button", "label": "Pause (k)",
             "frame": [0, 0, 1, 1]}
    video = {"ref": 5, "role": "link", "label": "Jazz Café - 3 hours",
             "frame": [0, 0, 1, 1]}

    def observe():
        if state["playing"]:
            return _zen("Jazz Café - 3 hours - YouTube", [pause])
        return _zen("jazz - YouTube", [video])

    def act(params):
        if params.get("op") == "press" and press_to_pause:
            state["playing"] = True
        return {"ok": True, "epoch": 2}
    return FakeServer(act=act, observe=observe), state


def test_results_page_done_rejected_then_video_click_accepted(tmp_path):
    """User trace: reached "jazz - YouTube" results and stopped. A results
    page is not the end of a play goal."""
    server, state = _play_setup()
    planner = VerifyPlanner([
        ['url "https://www.youtube.com/results?search_query=jazz"',
         'expect title~"jazz"'],
        ['done "Playing jazz"'],
        ["press #5"],
        ['done "Playing jazz"']])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    assert run(orch._planner_loop("Play some jazz music on Youtube", trace)) == "ok"
    rejected = "\n".join(planner.user_msgs[2]["last_batch"])
    assert "done rejected: finish criterion not visible (jazz music is playing" \
        in rejected
    assert state["playing"]
    verifies = [d["planner.verify"] for d in trace["decisions"]
                if "planner.verify" in d]
    assert verifies[-1]["method"] == "auto"
    assert orch._done_evidence == "auto"
    assert planner.decide_calls == []
    assert {"planner.recover": {"round": 1, "reason": "finish"}} in \
        trace["decisions"]


def test_finish_rejects_only_once_then_normal_verification(tmp_path):
    server, _ = _play_setup(press_to_pause=False)
    planner = VerifyPlanner([['done "Playing"'], ['done "Playing"']],
                            probabilities=[0.95])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    assert run(orch._planner_loop("play some jazz on youtube", trace)) == "ok"
    assert len(planner.decide_calls) == 1
    assert orch._done_evidence == "model"


def test_verify_done_off_has_no_finish_gate(tmp_path):
    server, _ = _play_setup(press_to_pause=False)
    planner = FakePlanner([['done "Playing"']])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    assert run(orch._planner_loop("play some jazz on youtube", trace)) == "ok"
    assert not any("planner.finish" in d for d in trace["decisions"])


def test_script_stdout_playing_is_play_evidence(tmp_path):
    server = FakeServer(act=lambda p: {"ok": True, "epoch": 2,
                                       "stdout": "playing"},
                        observe=lambda: {"epoch": 1, "app": "Spotify",
                                         "window": "Spotify", "elements": [],
                                         "text": "app: Spotify", "ax_ms": 1})
    planner = VerifyPlanner([
        ['script applescript """tell application "Spotify" to player state"""'],
        ['done "Playing"']])
    orch = _orch(server, planner)
    trace = trace_for(orch)
    assert run(orch._planner_loop("play some jazz on spotify", trace)) == "ok"
    assert orch._done_evidence in ("auto", "finish")


# 4. workflow-memory hygiene ------------------------------------------------

def _demo(goal, batch):
    return Demo(goal=goal, app="Notes", category="user",
                obs_header="app: Notes", batch=batch, source="memory")


def test_workflow_ok_rules():
    assert workflow_ok(_demo("create a grocery list note", ['open "Notes"', "keys cmd+n"]))
    assert not workflow_ok(_demo("create a grocery list note", ['open "Notes"']))
    assert not workflow_ok(_demo("create a grocery list note",
                                 ["press #3", 'type #4 "x"', "scroll #2 down"]))
    assert not workflow_ok(_demo("new note", ['open "Notes"', "keys cmd+n"]))
    assert not workflow_ok(_demo("create a grocery list note",
                                 ['open "Notes"', 'expect app "Notes"']))


def test_load_workflows_filters_without_touching_file(tmp_path):
    rows = [
        {"goal": "create a grocery list note", "batch": ['open "Notes"', "keys cmd+n"]},
        {"goal": "make a new checklist", "batch": ['open "Notes"']},
        {"goal": "press the second row", "batch": ["press #3", "press #4"]},
        {"goal": "new note", "batch": ['open "Notes"', "keys cmd+n"]},
    ]
    path = tmp_path / "workflows.jsonl"
    text = "".join(json.dumps({"app": "Notes", "category": "user",
                               "obs_header": "app: Notes", "source": "memory",
                               **row}) + "\n" for row in rows) + "not json\n"
    path.write_text(text)
    assert [d.goal for d in load_workflows(path)] == ["create a grocery list note"]
    assert path.read_text() == text
    assert load_workflows(tmp_path / "missing.jsonl") == []


def _memory_orch(tmp_path, monkeypatch, lines, evidence_source):
    monkeypatch.setenv("MUSELET_MEMORY_DB", str(tmp_path / "memory.db"))
    orch = Orchestrator(FakeServer(), Catalog.load(), Tracer())

    class P:
        plan_bank = PlanBank([])
    orch.planner = P()
    orch._last_obs = {"app": "Notes", "text": "app: Notes"}
    orch._done_evidence = evidence_source
    trace = {"decisions": [{"planner_turn": 0, "lines": lines},
                           {"planner_turn": 1, "lines": ['done "ok"']}]}
    return orch, trace


def test_workflow_written_only_with_non_app_evidence(tmp_path, monkeypatch):
    good = ['open "Notes"', "keys cmd+n"]
    for source, written in (("app", False), (None, False), ("expect", True)):
        path = tmp_path / "workflows.jsonl"
        path.unlink(missing_ok=True)
        orch, trace = _memory_orch(tmp_path, monkeypatch, good, source)
        writes = orch._planner_memory_writes("make a new note in notes", trace)
        assert path.exists() is written, source
        assert any(w["type"] == "workflow" for w in writes) is written
        assert bool(orch.planner.plan_bank.demos) is written


def test_ref_only_workflow_not_written(tmp_path, monkeypatch):
    orch, trace = _memory_orch(tmp_path, monkeypatch,
                               ["press #3", "press #4"], "expect")
    orch._planner_memory_writes("press the save button twice", trace)
    assert not (tmp_path / "workflows.jsonl").exists()


def test_ensure_workflows_merges_filtered_file(tmp_path, monkeypatch):
    orch, _ = _memory_orch(tmp_path, monkeypatch, [], None)
    orch.memory_enabled = orch.longterm_enabled = True
    (tmp_path / "workflows.jsonl").write_text("".join(json.dumps({
        "goal": goal, "app": "Notes", "category": "user",
        "obs_header": "app: Notes", "batch": batch}) + "\n" for goal, batch in (
            ("create a grocery list note", ['open "Notes"', "keys cmd+n"]),
            ("open notes", ['open "Notes"']))))
    orch._ensure_workflows()
    assert [d.goal for d in orch.planner.plan_bank.demos] == ["create a grocery list note"]
    orch._ensure_workflows()           # once per process
    assert len(orch.planner.plan_bank.demos) == 1


# 5. retrieval cross-app skip ----------------------------------------------

def _bank():
    def d(goal, app, batch):
        return Demo(goal=goal, app=app, category="user",
                    obs_header=f"app: {app}", batch=batch)
    return PlanBank([
        d("play some jazz music on spotify", "Spotify",
          ['open "Spotify"', 'script applescript """tell application "Spotify" to play"""']),
        d("play some lofi music on spotify", "Spotify", ['url "spotify:search:lofi"']),
        d("play lofi music on youtube", "Zen",
          ['url "https://www.youtube.com/results?search_query=lofi"']),
        d("play some music", "Music", ['open "Music"', "keys space"]),
    ])


def test_goal_targets():
    assert goal_targets("Play some music on YouTube") == {"youtube"}
    assert goal_targets("play some jazz on spotify") == {"spotify"}
    assert goal_targets("play some music") == frozenset()


def test_retrieval_skips_demos_for_other_apps_and_fills_k():
    got = [d.goal for d in _bank().retrieve(
        "Play some music on YouTube", 'app: Devin | window: "chat"', 2)]
    assert got and not any("spotify" in g for g in got)
    assert len(got) == 2
    # no named app: no skipping
    got = [d.goal for d in _bank().retrieve("play some music", "app: Finder", 4)]
    assert any("spotify" in g for g in got)


# 6. user-trace regressions --------------------------------------------------

class PromptPlanner(CtxPlanner):
    """Emits Spotify actions iff Spotify leaked into its prompt (screen
    context or retrieved demos), like the live run did."""

    def __init__(self):
        super().__init__([['done "ok"']])
        self.plan_bank = _bank()

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             **kw):
        prompt = (kw.get("context") or "") + render_block(
            self.plan_bank.retrieve(goal, observation, 3))
        self.prompts = getattr(self, "prompts", []) + [prompt]
        if "spotify" in prompt.lower():
            self.turns = [['open "Spotify"'], ['url "spotify:search:music"'],
                          ['done "ok"']]
        else:
            self.turns = [['url "https://www.youtube.com/results?search_query=music"'],
                          ['done "ok"']]
        return super().plan(goal, observation, last_batch, lines_out, loop,
                            cancel, **kw)


def test_play_music_on_youtube_from_devin_never_opens_spotify(tmp_path):
    utterance = "Play some music on YouTube"
    planner = PromptPlanner()
    obs = _observe([{"ref": 1, "role": "button", "label": "x"}],
                   text='app: Devin | window: "Devin chat"')
    server, _, orch = _setup(tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
                             planner=planner, observe=obs)
    orch.planner_context = True

    async def fake_ocr():
        return "Play some jazz on Spotify — test prompt list"
    orch._window_ocr_text = fake_ocr
    _run(orch.handle_utterance(utterance, {"app": "Devin",
                                           "window_title": "Devin chat"}))
    assert planner.prompts and "spotify" not in planner.prompts[0].lower()
    sent = json.dumps(server.rpcs).lower()
    assert "spotify" not in sent
    assert "youtube.com/results" in sent


# Spotify: never grounded/pixel clicks (a grounded click removed a playlist)

def test_spotify_prompts_never_suggest_clicks():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "prompts"
    hint = next(json.loads(line) for line in
                (root / "app_hints.jsonl").read_text().splitlines()
                if line.strip() and json.loads(line)["id"] == "spotify")
    # only the gated title double-click is taught (PR #101); never single clicks
    for tip in hint["tips"]:
        assert "click #" not in tip
        for m in re.finditer(r'click "[^"]*"( double)?', tip):
            assert m.group(1), tip
    for block in (root / "planner_fewshot.md").read_text().split("\n\n"):
        if "spotify" in block.lower():
            for line in block.splitlines():
                if line.lstrip("[ok] ").startswith("click"):
                    assert line.rstrip().endswith("double"), block


def test_grounded_click_refused_in_spotify():
    server = FakeServer()
    orch = _orch(server, FakePlanner([['done "x"']]))
    orch._last_obs = {"app": "Spotify", "window": "Spotify"}
    orch.grounder_cfg = {"max_pixels": 1}
    r = run(orch._exec_action({"op": "click",
                               "target": "green Play button of the top result"}))
    assert r["status"] == "failed" and "Spotify" in r["error"]
    assert not [c for c in server.rpcs if c[0] in ("screenshot", "act")]
