"""NativeUI (ui_only) planner gets fresh OCR screen context every turn."""
from fakes import FakeServer
from brain.catalog import Catalog
from brain.native_planner import NativeToolPlanner
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from test_fallback_planner import FakePlanner, _observe, _run, _setup
from test_planner_aux import _TextModel, _Worker


def _toolbar_obs(app="Numbers"):
    label = "Toolbar button with a long accessibility description " * 4
    return _observe(
        [{"ref": 1, "role": "button", "label": label}],
        text=f'app: {app} | window: "Untitled"\n#1 button "{label}"') | {
            "app": app, "window": "Untitled"}


class UIPlanner(FakePlanner):
    ui_only = True


def test_context_block_force_ocr_uses_ocr_over_thin_ax(tmp_path):
    utterance = "sort this table by amount, largest to smallest"
    server, _, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        observe=_toolbar_obs(), planner=FakePlanner([]))
    orch._ctx["app"] = "Numbers"
    calls = []
    async def ocr():
        calls.append(1)
        return "Date  Description  Amount  Balance"
    orch._window_ocr_text = ocr

    block, used = _run(orch._planner_context_block(
        _toolbar_obs(), utterance, force_ocr=True))
    assert used is True and calls == [1]
    assert "Date / Description / Amount / Balance" in block

    calls.clear()
    block, used = _run(orch._planner_context_block(
        _toolbar_obs(), utterance, force_ocr=False))
    # AX text >120 chars, not blind: no OCR, AX text used
    assert used is False and calls == []
    assert "Toolbar / button" in block


def test_native_ui_gets_fresh_ocr_each_turn(tmp_path):
    utterance = "sort this table by amount, largest to smallest"
    shots = iter(["OCR first snapshot", "OCR second snapshot"])

    def screenshot(_params):
        return {"path": "test.png"}
    def ocr(_params):
        return {"text": next(shots)}

    planner = UIPlanner([["wait 1"], ['done "Finished"']])
    server, tracer, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        handlers={"screenshot": screenshot, "ocr": ocr},
        observe=_toolbar_obs(), planner=planner)
    orch.planner_context = True
    orch._ctx["app"] = "Numbers"

    _run(orch.handle_utterance(utterance, {"app": "Numbers"}))

    assert planner.calls == 2
    assert "OCR / first / snapshot" in planner.user_msgs[0]["context"]
    assert "OCR / second / snapshot" in planner.user_msgs[1]["context"]
    assert "first" not in planner.user_msgs[1]["context"]
    assert tracer.rows[-1]["planner.context"]["turn"] == 1


def test_force_ocr_empty_falls_back_to_ax(tmp_path):
    utterance = "sort this table by amount, largest to smallest"
    server, _, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        observe=_toolbar_obs(), planner=FakePlanner([]))
    orch._ctx["app"] = "Numbers"
    calls = []
    async def ocr():
        calls.append(1)
        return ""
    orch._window_ocr_text = ocr

    block, used = _run(orch._planner_context_block(
        _toolbar_obs(), utterance, force_ocr=True))
    assert used is False and calls == [1]
    assert "Toolbar / button" in block


def test_force_ocr_never_captures_chat_ide_or_muselet(tmp_path):
    utterance = "sort this table by amount, largest to smallest"
    for app in ("Devin", "Muselet"):
        server, _, orch = _setup(
            tmp_path, {utterance: ("MULTI_STEP", 0.9)},
            observe=_toolbar_obs(app=app), planner=FakePlanner([]))
        orch._ctx["app"] = app
        calls = []
        async def ocr():
            calls.append(1)
            return "SHOULD NOT CAPTURE"
        orch._window_ocr_text = ocr
        block, used = _run(orch._planner_context_block(
            _toolbar_obs(app=app), utterance, force_ocr=True))
        assert used is False and calls == [], app
        assert "SHOULD NOT CAPTURE" not in block


def test_current_obs_app_wins_over_request_app_for_capture(tmp_path):
    """Request ctx says Devin (PTT app); the user switched to Numbers —
    the CURRENT frontmost app's screen is what gets OCR'd."""
    utterance = "sort this table by amount, largest to smallest"
    server, _, orch = _setup(
        tmp_path, {utterance: ("MULTI_STEP", 0.9)},
        observe=_toolbar_obs(), planner=FakePlanner([]))
    orch._ctx["app"] = "Devin"          # request-time app
    calls = []
    async def ocr():
        calls.append(1)
        return "Date  Description  Amount"
    orch._window_ocr_text = ocr

    block, used = _run(orch._planner_context_block(
        _toolbar_obs(app="Numbers"), utterance, force_ocr=True))
    assert used is True and calls == [1]
    # request metadata still labelled as request context
    assert 'app "Devin"' in block
    assert "Date / Description / Amount" in block


def test_native_tool_planner_marked_ui_only():
    assert NativeToolPlanner.ui_only is True


# --- done-verification uses its own fresh OCR under ui_only ---

def _verify_orch(tmp_path, obs, ui_only, ocr_text=""):
    orch = Orchestrator(
        FakeServer(observe=lambda: obs), Catalog.load(),
        Tracer(tmp_path / "traces"))

    planner = _TextModel()
    planner.ui_only = ui_only
    orch.planner_aux = planner
    orch.planner = planner
    calls = []

    async def ocr():
        calls.append(1)
        return ocr_text
    orch._window_ocr_text = ocr
    return orch, calls


def test_verify_done_ui_only_passes_fresh_ocr_to_verifier(
        tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: _Worker())
    obs = _toolbar_obs()          # long toolbar AX, no table data
    orch, calls = _verify_orch(
        tmp_path, obs, ui_only=True,
        ocr_text="Verification fresh screen Amount sorted")

    ok, p_yes, got_obs, _missing = _run(orch._verify_done(
        "sort this table by amount, largest to smallest",
        [], {"decisions": []}))

    assert calls == [1]           # its own fresh capture, not cached
    state, _q = orch.planner.decide_calls[0][0]
    assert "Verification / fresh / screen" in state
    assert "Planning old screen" not in state
    assert ok is True


def test_verify_done_ui_only_empty_ocr_safe(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: _Worker())
    orch, calls = _verify_orch(
        tmp_path, _toolbar_obs(), ui_only=True, ocr_text="")
    orch.planner.probabilities = {"true": 0.0, "false": 1.0}

    ok, _p, _obs, _m = _run(orch._verify_done(
        "sort this table by amount", [], {"decisions": []}))

    assert calls == [1]
    assert ok is False            # empty OCR -> no false yes


def test_verify_done_ui_only_skips_private_app(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: _Worker())
    obs = _toolbar_obs(app="Devin")
    orch, calls = _verify_orch(
        tmp_path, obs, ui_only=True, ocr_text="SECRET IDE TEXT")
    orch.planner.probabilities = {"true": 0.0, "false": 1.0}
    orch._ctx["app"] = "Devin"

    _run(orch._verify_done(
        "sort this table by amount", [], {"decisions": []}))

    assert calls == []            # context block refused the capture
    state, _q = orch.planner.decide_calls[0][0]
    assert "SECRET IDE TEXT" not in state


def test_verify_done_non_ui_does_not_force_ocr(tmp_path, monkeypatch):
    monkeypatch.setattr("brain.planner.worker", lambda: _Worker())
    obs = _toolbar_obs()          # >200 chars of AX text
    orch, calls = _verify_orch(
        tmp_path, obs, ui_only=False, ocr_text="SHOULD NOT CAPTURE")

    _run(orch._verify_done(
        "sort this table by amount", [], {"decisions": []}))

    assert calls == []
