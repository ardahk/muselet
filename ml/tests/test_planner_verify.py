import re

from test_planner_loop import _diff_orch, run, trace_for, FakePlanner

from brain import cli


class VerifyPlanner(FakePlanner):
    def __init__(self, turns, probabilities=(), missing="the save dialog is still open"):
        super().__init__(turns)
        self.probabilities = list(probabilities)
        self.missing = missing
        self.decide_calls = []
        self.generate_calls = []

    def decide(self, state, question):
        self.decide_calls.append((state, question))
        p_yes = self.probabilities.pop(0) if self.probabilities else 0.9
        return {"true": p_yes, "false": 1 - p_yes}

    def generate(self, system, user, max_tokens=48):
        self.generate_calls.append((system, user, max_tokens))
        return self.missing


def _orch(tmp_path, turns, probabilities=(), missing=None):
    planner = VerifyPlanner(
        turns, probabilities,
        "the save dialog is still open" if missing is None else missing)
    orch = _diff_orch(
        tmp_path, turns,
        lambda _params: {"ok": True, "epoch": 2, "diff_text": ""})
    orch.planner = planner
    return orch, planner


def _decisions(trace, key):
    return [entry[key] for entry in trace["decisions"] if key in entry]


def test_previous_expect_evidence_accepts_done_without_model(tmp_path):
    orch, planner = _orch(
        tmp_path, [['press #1', 'expect appears "Saved"'],
                   ['done "Saved"']])
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "ok"
    assert planner.decide_calls == []
    assert orch.server.uis[-1] == "success"
    assert _decisions(trace, "planner.verify")[-1] == {
        "method": "expect", "p_yes": None, "ms": 0.0, "result": True}


def test_model_no_replans_and_model_yes_accepts_done(tmp_path):
    orch, planner = _orch(
        tmp_path, [['done "Saved"'], ['done "Saved"']], [0.2, 0.9])
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "ok"
    assert "verification failed: the save dialog is still open" in \
        "\n".join(planner.user_msgs[1]["last_batch"])
    assert [entry["p_yes"] for entry in _decisions(
        trace, "planner.verify")] == [0.2, 0.9]
    assert _decisions(trace, "planner.recover")[0] == {
        "round": 1, "reason": "verify"}


def test_wait_does_not_clear_last_consequential_expect(tmp_path):
    orch, planner = _orch(
        tmp_path,
        [['press #1', 'expect appears "Saved"'], ["wait 10"],
         ['done "Saved"']])
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "ok"
    assert planner.decide_calls == []
    assert _decisions(trace, "planner.verify")[-1]["method"] == "expect"


def test_verification_recovery_budget_ends_with_honest_failure(tmp_path):
    orch, _ = _orch(
        tmp_path, [['done "Saved"']] * 3, [0.1, 0.1, 0.1])
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "failed"
    assert orch.server.uis[-1] == "confused"
    assert "success" not in orch.server.uis
    bubble = orch.server.said[-1]
    assert bubble.startswith("Not finished:")
    assert len(bubble.split()) <= 12
    assert not re.search(r"\b(done|success)\b", bubble, re.IGNORECASE)
    assert _decisions(trace, "planner.recover")[-1] == {
        "round": 3, "reason": "verify", "exhausted": True}


def test_turn_limit_uses_honest_failure_in_verify_mode(tmp_path):
    orch, _ = _orch(tmp_path, [["wait 1"]] * 12)
    trace = trace_for(orch)

    assert run(orch._planner_loop("complete the task", trace)) == "failed"
    assert orch.server.uis[-1] == "confused"
    assert orch.server.said[-1].startswith("Not finished:")
    assert len(orch.server.said[-1].split()) <= 12
    assert _decisions(trace, "planner.recover")[-1] == {
        "round": 0, "reason": "turn_limit", "exhausted": True}


def test_alternating_expect_failures_exhaust_recovery_budget(tmp_path):
    turns = [
        ['press #1', 'expect appears "A"'],
        ['press #2', 'expect appears "B"'],
        ['press #3', 'expect appears "C"'],
        ['press #4', 'expect appears "D"'],
        ['press #5', 'expect appears "E"'],
    ]
    orch, _ = _orch(tmp_path, turns)
    verification = iter([False, True, False, True, False])

    def verify(_params):
        ok = next(verification)
        return {"ok": ok, "observed": "visible" if ok else "not visible"}

    orch.server.handlers["verify"] = verify
    trace = trace_for(orch)

    assert run(orch._planner_loop("complete the task", trace)) == "failed"
    recoveries = _decisions(trace, "planner.recover")
    assert [entry["round"] for entry in recoveries
            if "exhausted" not in entry] == [1, 2, 3]
    assert recoveries[-1]["exhausted"] is True
    assert orch.server.said[-1].startswith("Not finished:")


def test_missing_text_claiming_done_uses_safe_fallback(tmp_path):
    orch, _ = _orch(tmp_path, [[]], missing="Done already")

    assert run(orch._missing_text("save the file", [], "empty")) == \
        "the goal isn't visible on screen yet"


def test_replanned_send_still_requires_confirmation(tmp_path):
    orch, planner = _orch(
        tmp_path,
        [['done "Sent"'], ["press #1"], ['done "Sent"']],
        [0.1, 0.9])
    orch.server.observe = lambda: {
        "epoch": 1, "app": "Messages", "window": "New Message",
        "text": 'app: Messages | window: "New Message"\n#1 button "Send"',
        "elements": [{"ref": 1, "role": "button", "label": "Send",
                      "enabled": True, "frame": [0, 0, 10, 10]}],
    }
    act = orch.server.act

    def act_after_confirm(params):
        assert orch.server.confirms
        return act(params)

    orch.server.act = act_after_confirm
    trace = trace_for(orch)

    assert run(orch._planner_loop("send the message", trace)) == "ok"
    assert orch.server.confirms
    assert len(planner.decide_calls) == 2


def test_permission_prompt_during_verification_never_accepts_done(tmp_path):
    orch, planner = _orch(tmp_path, [['done "Allowed"']], [0.9])
    observations = iter([
        {"epoch": 1, "app": "Finder", "text": "app: Finder", "elements": []},
        {"epoch": 2, "app": "SecurityAgent", "window": "Accessibility",
         "text": "Accessibility permission", "elements": []},
    ])
    orch.server.observe = lambda: next(observations)
    trace = trace_for(orch)

    assert run(orch._planner_loop("allow access", trace)) == "awaiting_user"
    assert planner.decide_calls == []
    assert "success" not in orch.server.uis


def test_fifth_action_expect_is_used_as_done_evidence(tmp_path):
    lines = [f"press #{i}" for i in range(1, 6)]
    lines += ['expect appears "X"']
    orch, planner = _orch(tmp_path, [lines, ['done "X"']])
    trace = trace_for(orch)

    assert run(orch._planner_loop("complete five actions", trace)) == "ok"
    verify_calls = [params for method, params in orch.server.rpcs
                    if method == "verify"]
    assert verify_calls[-1] == {"expect": 'appears "X"'}
    assert planner.decide_calls == []
    assert _decisions(trace, "planner.verify")[-1]["method"] == "expect"


def test_done_expect_passes_without_model_verification(tmp_path):
    orch, planner = _orch(
        tmp_path, [['done "Saved"', 'expect appears "Saved"']])
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "ok"
    assert planner.decide_calls == []
    assert [params for method, params in orch.server.rpcs
            if method == "verify"] == [
                {"expect": 'appears "Saved"'}]
    assert _decisions(trace, "planner.verify")[-1]["method"] == "expect"


def test_done_expect_failure_replans_with_failure_in_history(tmp_path):
    orch, planner = _orch(
        tmp_path,
        [['done "Saved"', 'expect appears "Saved"'],
         ['ask "What should I do?"']])
    orch.server.handlers["verify"] = lambda _params: {
        "ok": False, "observed": "not visible"}
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "awaiting_user"
    assert "verification failed: expect failed: not visible" in \
        "\n".join(planner.user_msgs[1]["last_batch"])
    assert planner.decide_calls == []


def test_verify_done_off_keeps_legacy_done_acceptance(tmp_path):
    orch, planner = _orch(tmp_path, [['done "Saved"']])
    orch.verify_done = False
    trace = trace_for(orch)

    assert run(orch._planner_loop("save the file", trace)) == "ok"
    assert planner.decide_calls == []
    assert orch.server.uis[-1] == "success"


def test_cli_verify_done_flag_defaults_on_and_can_be_disabled():
    args, _ = cli.build_parser(["serve"])
    assert args.verify_done == "on"
    args, _ = cli.build_parser(["serve", "--verify-done", "off"])
    assert args.verify_done == "off"


def test_cli_passes_verify_done_setting_to_serve(monkeypatch):
    seen = {}

    async def fake_serve(port, model, planner_model, planner_kw=None,
                         args_model=None, escalate_model=None, grounder=None,
                         verify_done=True):
        seen["verify_done"] = verify_done

    monkeypatch.setattr(cli, "serve", fake_serve)
    monkeypatch.setattr(cli, "_resolve_model", lambda model: model)
    cli.run_cmd(*cli.build_parser(["serve", "--verify-done", "off"]))
    assert seen["verify_done"] is False


def test_verification_uses_ocr_only_for_short_observations(tmp_path):
    short, short_planner = _orch(tmp_path, [['done "Saved"']], [0.9])
    short.server.observe = lambda: {
        "epoch": 1, "app": "Finder", "text": "app: Finder", "elements": []}
    short.server.handlers["screenshot"] = lambda _params: {
        "ok": True, "path": "/tmp/window.png"}
    short.server.handlers["ocr"] = lambda _params: {
        "ok": True, "text": "The file is saved"}
    short_trace = trace_for(short)

    assert run(short._planner_loop("save the file", short_trace)) == "ok"
    assert "Screen text (OCR):\nThe file is saved" in \
        short_planner.decide_calls[0][0]
    assert any(method == "screenshot" for method, _ in short.server.rpcs)

    long, long_planner = _orch(
        tmp_path, [['done "Saved"']], [0.9])
    long_text = "x" * 250
    long.server.observe = lambda: {
        "epoch": 1, "app": "Finder", "text": long_text, "elements": []}
    long_trace = trace_for(long)

    assert run(long._planner_loop("save the file", long_trace)) == "ok"
    assert "Screen text (OCR):" not in long_planner.decide_calls[0][0]
    assert not any(method == "screenshot" for method, _ in long.server.rpcs)
