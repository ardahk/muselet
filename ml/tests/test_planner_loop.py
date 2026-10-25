"""Planner-loop tests: scripted FakePlanner on the real MLX worker thread +
the fake WS hands. Covers streaming, done validation, replan paths, ask/
confirm continuation, cancel, injection guards and brain-executor dispatch."""

import asyncio
import sys
import time
import types

import pytest
from brain import protocol
from brain.catalog import Catalog
from brain.memory import WorkingMemory
from brain.orchestrator import Orchestrator
from brain.server import BrainServer
from brain.traces import Tracer
from test_orchestrator import FakeHands


class FakePlanner:
    """plan() matches Planner.plan's signature; runs on the MLX worker
    thread, emits each canned line ~20 ms apart, then the None sentinel."""

    def __init__(self, turns, history="repr"):
        self.turns = turns          # list of turn -> list of lines
        self.history = history      # older tests pin the legacy repr lines
        self.calls = 0
        self.user_msgs = []
        self.cancelled = None
        self.finished_emitting = asyncio.Event() if False else None

    def plan(self, goal, observation, last_batch, lines_out, loop,
             cancel, hint=None, script_output=None, recent=None):
        idx = min(self.calls, len(self.turns) - 1)
        self.calls += 1
        self.user_msgs.append({
            "goal": goal, "obs": observation,
            "last_batch": last_batch, "hint": hint,
            "script_output": script_output, "recent": recent})
        self.cancelled = cancel
        for line in self.turns[idx]:
            if cancel.is_set():
                break
            time.sleep(0.02)
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": self.turns[idx], "ttft_ms": 5.0,
                "decode_tok_s": 20.0, "tokens": 12, "plan_ms": 100.0}


def _mk(port, planner, hands):
    server = BrainServer(port=port)
    orch = Orchestrator(server, Catalog.load(), Tracer())
    orch.planner = planner
    return server, orch


def _obs_elements(els, app="Finder", window="Recents"):
    return {"epoch": 1, "app": app, "window": window,
            "focused_ref": 1, "elements": els,
            "text": f'app: {app} | window: "{window}"', "ax_ms": 1}


async def _up(server, hands, orch, port):
    await server.start()
    await hands.connect(port)
    server.on_utterance = lambda t, f, c=None: orch.handle_utterance(t, c)


def run(coro):
    return asyncio.run(coro)


def trace_for(orch, text="goal"):
    return {"utterance": text, "decisions": []}


def test_streaming_first_action_before_decode_done(tmp_path):
    """(a) first act rpc must go out while the planner is still emitting."""
    hands = FakeHands()
    planner = FakePlanner([[f"press #{i}" for i in range(1, 4)]])
    server, orch = _mk(0, planner, hands)
    first_act_at = [None]
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "act" and first_act_at[0] is None:
            first_act_at[0] = planner.calls == 1  # still inside plan()
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)

    async def go():
        server.port = 9901
        await _up(server, hands, orch, 9901)
        out = await orch._planner_loop("press things", trace_for(orch))
        await hands.close(); await server.close()
        return out
    out = run(go())
    assert out in ("ok", "failed")
    assert first_act_at[0] is True          # act sent while plan() running


def test_done_alone_after_clean_batch(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([["press #1"], ['done "all set"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9902
        await _up(server, hands, orch, 9902)
        out = await orch._planner_loop("do it", trace_for(orch))
        await asyncio.sleep(0.1)
        await hands.close(); await server.close()
        return out
    assert run(go()) == "ok"
    assert any(m.get("t") == "ui" and m.get("mascot") == "success"
               for m in hands.messages)


def test_planner_loop_passes_recent_memory(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([["press #1"], ['done "finished"']])
    planner.last_hint_ids = ["spotify"]
    server, orch = _mk(0, planner, hands)
    orch.memory = WorkingMemory()
    orch.memory.record(
        "open Wikipedia", "open https://en.wikipedia.org/", "open_url",
        {"url": "https://en.wikipedia.org/"}, True, {"app": "Zen"},
        t=time.time())
    orch.tracer = Tracer(tmp_path / "traces")

    async def go():
        server.port = 9907
        await _up(server, hands, orch, 9907)
        trace = trace_for(orch)
        out = await orch._planner_loop("do it", trace)
        await hands.close()
        await server.close()
        return out, trace

    out, trace = run(go())
    assert out == "ok"
    assert any(decision.get("app_hints") == ["spotify"]
               for decision in trace["decisions"])
    assert isinstance(next(d["turn_ms"] for d in trace["decisions"]
                           if "planner_turn" in d), (int, float))
    assert planner.user_msgs[0]["recent"] == orch.memory.recent_lines(5)


def test_done_mixed_rejected(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([
        ["press #1", 'done "early"'],      # done mixed with an action
        ['done "for real"'],
    ])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9903
        await _up(server, hands, orch, 9903)
        out = await orch._planner_loop("do it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    run(go())
    # the second turn's Last batch must carry the rejected-done note
    lb = planner.user_msgs[1]["last_batch"]
    assert lb and any("not verified" in l for l in lb)


def test_expect_failure_replans(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([
        ["press #1", "expect appears \"Won't\""],
        ['done "recovered"'],
    ])
    server, orch = _mk(0, planner, hands)
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "verify":
            return protocol.rpc_result(
                msg["id"], True, {"ok": False, "observed": "nothing"})
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)

    async def go():
        server.port = 9904
        await _up(server, hands, orch, 9904)
        out = await orch._planner_loop("do it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    run(go())
    lb = planner.user_msgs[1]["last_batch"]
    assert lb and any("expect failed" in l for l in lb)


def test_stale_ref_replans(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([
        ["press #1"], ['done "ok"'],
    ])
    hands.act_results = {"press": {"ok": False, "error": "stale_ref"}}
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9905
        await _up(server, hands, orch, 9905)
        out = await orch._planner_loop("do it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    assert run(go()) == "ok"
    assert planner.calls == 3


def test_script_block_one_action(tmp_path):
    hands = FakeHands()
    code = 'tell app "Numbers"\nset value of cell "B5" to 1\nreturn 1'
    script_line = f'script applescript """{code}\n"""'
    planner = FakePlanner([[script_line], ['done "wrote"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9906
        await _up(server, hands, orch, 9906)
        out = await orch._planner_loop("write cell", trace_for(orch))
        await hands.close(); await server.close()
        return out
    run(go())
    script_rpcs = [m for m in hands.rpcs
                   if m["method"] == "act" and m["params"].get("op") == "script"]
    assert len(script_rpcs) == 1
    assert 'set value' in script_rpcs[0]["params"]["code"]


def test_ask_then_answer_continues(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([
        ['ask "which folder?"'],
        ['done "got it"'],
    ])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9907
        await _up(server, hands, orch, 9907)
        out = await orch._planner_loop("move it", trace_for(orch))
        assert out == "awaiting_user"
        assert orch._pending_task
        out2 = await orch.handle_utterance("the blue one")
        await hands.close(); await server.close()
        return out2
    run(go())
    assert 'User answer: "the blue one"' in planner.user_msgs[1]["goal"]


def test_confirm_yes_no_double(tmp_path):
    hands = FakeHands()
    hands.confirm_yes = True
    # observe exposes a "Send" button so the press is dangerous
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "observe":
            return protocol.rpc_result(msg["id"], True, _obs_elements(
                [{"ref": 1, "role": "button", "label": "Send",
                  "enabled": True, "frame": [0, 0, 10, 10]}],
                app="Messages"))
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)
    planner = FakePlanner([['confirm "send it?"', "press #1"], ['done "sent"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9908
        await _up(server, hands, orch, 9908)
        out = await orch._planner_loop("send it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    run(go())
    assert len(hands.sent_confirm_replies) == 1   # no double confirm


@pytest.mark.parametrize("actions", [
    ['confirm "Open settings?"', "press #2", "press #1"],
    ['confirm "Send it?"', "press #1", "press #1"],
], ids=["harmless_action_clears_confirm", "two_dangerous_actions_one_confirm"])
def test_brain14_confirm_covers_only_next_action(actions):
    hands = FakeHands()
    hands.confirm_yes = True
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "observe":
            return protocol.rpc_result(msg["id"], True, _obs_elements(
                [{"ref": 1, "role": "button", "label": "Send",
                  "enabled": True, "frame": [0, 0, 10, 10]},
                 {"ref": 2, "role": "button", "label": "Settings",
                  "enabled": True, "frame": [20, 0, 10, 10]}],
                app="Messages"))
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)
    planner = FakePlanner([actions, ['done "ok"']])
    server, orch = _mk(9961, planner, hands)

    async def go():
        await _up(server, hands, orch, 9961)
        try:
            await orch._planner_loop("open settings", trace_for(orch))
        finally:
            await hands.close()
            await server.close()
    run(go())
    confirms = [m for m in hands.messages if m.get("t") == "confirm"]
    assert len(confirms) == 2
    presses = [m["params"]["ref"] for m in hands.rpcs
               if m["method"] == "act" and m["params"].get("op") == "press"]
    assert presses == ([2, 1] if "press #2" in actions else [1, 1])


def test_confirm_no_cancels(tmp_path):
    hands = FakeHands()
    hands.confirm_yes = False
    planner = FakePlanner([['confirm "go?"', "press #1"]])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9909
        await _up(server, hands, orch, 9909)
        out = await orch._planner_loop("do it", trace_for(orch))
        await hands.close(); await server.close()
        return out
    assert run(go()) == "cancelled"
    assert not [m for m in hands.rpcs if m["method"] == "act"]


def test_cancel_stops_decode(tmp_path):
    hands = FakeHands()
    planner = FakePlanner([[f"press #{i}" for i in range(1, 5)]])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9910
        await _up(server, hands, orch, 9910)
        task = asyncio.create_task(
            orch._planner_loop("do it", trace_for(orch)))
        await asyncio.sleep(0.06)      # mid-emit
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await hands.close(); await server.close()
        return planner.cancelled.is_set() if planner.cancelled else False
    assert run(go()) is True


def test_injection_send_needs_confirm(tmp_path):
    hands = FakeHands()
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "observe":
            return protocol.rpc_result(msg["id"], True, _obs_elements(
                [{"ref": 1, "role": "button", "label": "Send",
                  "enabled": True, "frame": [0, 0, 10, 10]}],
                app="Messages"))
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)
    # a planner that just presses Send with no confirm (injected text)
    planner = FakePlanner([["press #1"]])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9911
        await _up(server, hands, orch, 9911)
        out = await orch._planner_loop("say hi", trace_for(orch))
        await asyncio.sleep(0.1)
        await hands.close(); await server.close()
        return out
    run(go())
    confirms = [m for m in hands.messages if m.get("t") == "confirm"]
    assert confirms, "no confirm was injected for a dangerous press"


def test_type_enter_messages_confirms(tmp_path):
    hands = FakeHands()
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "observe":
            return protocol.rpc_result(msg["id"], True, _obs_elements(
                [{"ref": 2, "role": "textfield", "label": "Message",
                  "enabled": True, "frame": [0, 0, 10, 10]}],
                app="Messages"))
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)
    planner = FakePlanner([['type #2 "hello" enter']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9912
        await _up(server, hands, orch, 9912)
        out = await orch._planner_loop("msg", trace_for(orch))
        await asyncio.sleep(0.1)
        await hands.close(); await server.close()
        return out
    run(go())
    assert [m for m in hands.messages if m.get("t") == "confirm"]


def test_brain_executor_skill_goes_to_tools(tmp_path):
    hands = FakeHands()
    called = {}

    async def fake_run(orch, args, utterance):
        called.update(args=args, utterance=utterance)
        return "ok"

    fake_mod = types.ModuleType("brain.tools.finance_review")
    fake_mod.run = fake_run
    sys.modules["brain.tools.finance_review"] = fake_mod
    planner = FakePlanner([['skill finance_review task="burn"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9913
        await _up(server, hands, orch, 9913)
        out = await orch._planner_loop("review burn", trace_for(orch))
        await hands.close(); await server.close()
        return out
    run(go())
    assert called["args"] == {"task": '"burn"'.strip('"')}
    assert not [m for m in hands.rpcs
                if m["method"] == "skill"
                and m["params"].get("name") == "finance_review"]
    del sys.modules["brain.tools.finance_review"]


# ---------- act diffs feed the next turn (no observe RPC) ----------

from fakes import FakeServer, _skill_rpcs

_OBS0 = 'app: Finder | window: "Recents" | focused: #4\n#1 button "Back"\n' \
        '#4 textfield "Search" value=""'


def _diff_orch(tmp_path, turns, act):
    srv = FakeServer(act=act, observe=lambda: {
        "epoch": 1, "app": "Finder", "window": "Recents", "focused_ref": 4,
        "elements": [{"ref": 1, "role": "button", "label": "Back",
                      "frame": [0, 0, 10, 10]}], "text": _OBS0, "ax_ms": 1})
    o = Orchestrator(srv, Catalog.load(), Tracer(tmp_path / "t"))
    o.planner = FakePlanner(turns)
    return o


def test_turn_obs_from_act_diff_without_observe(tmp_path):
    diffs = iter(['~ #4 value="hel"', '+ #31 button "Export"\n- #1'])
    o = _diff_orch(tmp_path, [['type #4 "hel"', 'press #31'], ['done "ok"'], ['done "ok"']],
                   lambda p: {"ok": True, "epoch": 2,
                              "diff_text": next(diffs)})
    tr = trace_for(o)
    assert run(o._planner_loop("search", tr)) == "ok"
    # unverified done -> one fresh observe, then accepted (planner-13)
    assert o.server.methods() == ["observe", "act", "act", "observe"]
    obs2 = o.planner.user_msgs[1]["obs"]
    assert obs2.startswith('app: Finder | window: "Recents" | focused: #4\n'
                    '#4 textfield "Search" value="hel"\n#31 button "Export"')
    assert "Finish when:" in obs2
    assert {"obs_from_diff": 1, "n_diffs": 2} in tr["decisions"]


def test_empty_diff_still_reused(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ['done "a"'], ['done "b"']],
                   lambda p: {"ok": True, "diff_text": ""})
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    # done on the diff view is rejected once, then a fresh observe (planner-13)
    assert o.server.methods() == ["observe", "act", "observe"]
    assert o.server.said[-1] == "b"
    assert o.planner.user_msgs[1]["obs"] == _OBS0


@pytest.mark.parametrize("res", [
    {"ok": True, "diff_text": "", "full": True},
    {"ok": True, "diff_text": "~ #4 value=\"x\"", "truncated": True},
    {"ok": True},                                   # no diff_text
])
def test_full_truncated_or_missing_diff_observes(tmp_path, res):
    o = _diff_orch(tmp_path, [["press #1"], ['done "ok"'], ['done "ok"']], lambda p: res)
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.methods() == ["observe", "act", "observe"]


def test_skill_in_batch_breaks_diff_chain(tmp_path):
    o = _diff_orch(tmp_path, [["press #1", "skill mute on=true"], ['done "ok"'], ['done "ok"']],
                   lambda p: {"ok": True, "diff_text": ""})
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.methods() == ["observe", "act", "skill", "observe"]


def test_failed_turn_with_diff_reuses_it(tmp_path):
    seq = iter([{"ok": False, "error": "expect_failed: x",
                 "diff_text": '~ #4 value="a"'},
                {"ok": True, "diff_text": ""}])
    o = _diff_orch(tmp_path, [["press #1"], ["press #4"], ['done "ok"'], ['done "ok"']],
                   lambda p: next(seq))
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    # unverified done -> one fresh observe, then accepted (planner-13)
    assert o.server.methods() == ["observe", "act", "act", "observe"]
    assert 'value="a"' in o.planner.user_msgs[1]["obs"]


def test_answer_by_code_skips_model(tmp_path):
    o = _diff_orch(tmp_path, [['done "x"']], lambda p: {"ok": True})
    called = []
    o.planner.generate = lambda *a: called.append(a) or "model"
    tr = trace_for(o)
    assert run(o._answer("what's 15 percent of 80", tr)) == "ok"
    assert o.server.said == ["15% of 80 is 12"] and not called
    assert {"calc": "15% of 80 is 12", "calc_target": "bubble"} in tr["decisions"]
    run(o._answer("who wrote Hamlet", tr))
    assert len(called) == 1 and o.server.said[-1] == "model"


def test_regex_fallback_answers_math(tmp_path):
    o = _diff_orch(tmp_path, [['done "x"']], lambda p: {"ok": True})
    o.planner = None
    assert run(o.handle_utterance("what's 7 times 8")) == {"outcome": "ok"}
    assert o.server.said == ["7 times 8 is 56"]
    assert "observe" not in o.server.methods()


# ---------- planner robustness: prose lines and the loop guard (brain-3) ----------

STUCK = "I'm stuck on that, can you help?"


def test_planner_skips_prose_and_prefixes_skill(tmp_path):
    turns = [["The previous action failed because TextEdit was closed.",
              "</think>", "```", 'open_app app="TextEdit"', "```"],
             ['done "Opened TextEdit"']]
    o = _diff_orch(tmp_path, turns, lambda p: {"ok": True})
    tr = trace_for(o)
    assert run(o._planner_loop("open textedit", tr)) == "ok"
    assert _skill_rpcs(o.server) == [("open_app", {"app": "TextEdit"})]
    assert "ignored 4 non-action lines" in o.planner.user_msgs[1]["last_batch"]
    assert {"skipped_lines": turns[0][:3] + ["```"]} in tr["decisions"]


def test_loop_guard_same_action_twice(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"]],
                   lambda p: {"ok": False, "error": "no such ref"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 2
    assert o.server.said[-1] == STUCK and o.server.uis[-1] == "confused"
    assert {"loop_guard": "same_action", "line": "press #1"} in tr["decisions"]
    assert o._pending_task["goal"] == "go"


def test_loop_guard_same_action_normalized(tmp_path):
    o = _diff_orch(tmp_path, [['type #1 "hi"'], ['type  #1   "hi"']],
                   lambda p: {"ok": False, "error": "x"})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 2


def test_loop_guard_three_failed_turns(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ["press #3"],
                              ["press #4"]],
                   lambda p: {"ok": False, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "awaiting_user"
    assert o.planner.calls == 3
    assert any(d.get("loop_guard") == "3_failed_turns" for d in tr["decisions"])


def test_loop_guard_prose_only_turns(tmp_path):
    o = _diff_orch(tmp_path, [["I will now open the app."]],
                   lambda p: {"ok": True})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 3 and o.server.said[-1] == STUCK


def test_loop_guard_parse_errors_same_line(tmp_path):
    o = _diff_orch(tmp_path, [["press 4"]], lambda p: {"ok": True})
    assert run(o._planner_loop("go", trace_for(o))) == "awaiting_user"
    assert o.planner.calls == 2


def test_loop_guard_resets_after_success(tmp_path):
    o = _diff_orch(tmp_path, [["press #1"], ["press #2"], ["press #1"],
                              ['done "ok"']],
                   lambda p: {"ok": p.get("ref") != 1, "error": "x"})
    tr = trace_for(o)
    assert run(o._planner_loop("go", tr)) == "ok"
    assert not any("loop_guard" in d for d in tr["decisions"])


# ---------- planner turn ends: ui ms, done, tool fallback, capped obs (lead review) ----------

def test_planner_final_ui_carries_total_ms(tmp_path):
    o = _diff_orch(tmp_path, [['done "ok"']], lambda p: {"ok": True})
    o._t_final = time.perf_counter() - 0.5
    o._first_action_ms = 1.0
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.ui_ms[-1] >= 500


def test_done_after_passing_expect_needs_no_extra_observe(tmp_path):
    o = _diff_orch(tmp_path, [["press #1", 'expect appears "Saved"'],
                              ['done "ok"']],
                   lambda p: {"ok": True, "diff_text": ""})
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.methods() == ["observe", "act", "verify"]


def test_brain_tool_fallback_ends_planner(tmp_path, monkeypatch):
    from brain import tools

    async def fb(*a, **k):
        return "fallback"
    monkeypatch.setattr(tools, "run", fb)
    o = _diff_orch(tmp_path, [["skill finance_review task=review"]] * 5,
                   lambda p: {"ok": True})
    assert run(o._planner_loop("review", trace_for(o))) == "fallback"
    assert o.server.said == ["That workflow is almost ready"]
    assert len(o.planner.user_msgs) == 1


@pytest.mark.parametrize("obs_extra", [
    {"truncated": True},
    {"elements": [{"ref": i, "role": "button", "label": f"b{i}",
                   "frame": [0, 0, 1, 1]} for i in range(150)]},
])
def test_capped_observation_never_rebuilt_from_diff(tmp_path, obs_extra):
    o = _diff_orch(tmp_path, [["press #1"], ['done "ok"']],
                   lambda p: {"ok": True, "diff_text": "- #1"})
    base = o.server.observe()
    o.server.observe = lambda: dict(base, **obs_extra)
    assert run(o._planner_loop("go", trace_for(o))) == "ok"
    assert o.server.methods() == ["observe", "act", "observe"]


# ---------- login-page hint and no-op press loop guard (first use) ----------

class _StreamingFakePlanner:
    def __init__(self, turns):
        self.turns = turns
        self.calls = 0
        self.login_hints = []
        self.history = "dsl"

    def plan(self, goal, observation, last_batch, lines_out, loop, cancel,
             hint=None, script_output=None, login_page=False):
        self.login_hints.append(login_page)
        lines = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        for line in lines:
            loop.call_soon_threadsafe(lines_out.put_nowait, line)
        loop.call_soon_threadsafe(lines_out.put_nowait, None)
        return {"lines": lines, "ttft_ms": 1, "decode_tok_s": 1,
                "tokens": 1}


def test_planner_loop_passes_login_page_hint(tmp_path):
    async def go():
        server = FakeServer(observe=lambda: {
            "epoch": 1, "app": "Chrome", "window": "Sign in",
            "focused_ref": None, "elements": [],
            "text": "app: Chrome | window: Sign in | Password",
            "ax_ms": 1})
        orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
        planner = _StreamingFakePlanner([['done "ok"']])
        orch.planner = planner
        outcome = await orch._planner_loop("continue", {"decisions": []})
        return outcome, planner

    outcome, planner = asyncio.run(go())
    assert outcome == "ok"
    assert planner.login_hints == [True]


def test_identical_noop_presses_trip_loop_guard(tmp_path):
    async def go():
        server = FakeServer(act=lambda p: {
            "ok": True, "epoch": 2, "diff_text": ""}, observe=lambda: {
                "epoch": 1, "app": "Notes", "window": "Notes",
                "focused_ref": None, "elements": [
                    {"ref": 1, "role": "button", "label": "New Note",
                     "frame": [0, 0, 20, 20]}],
                "text": 'app: Notes | window: "Notes"\n'
                        '#1 button "New Note"', "ax_ms": 1})
        orch = Orchestrator(server, Catalog.load(), Tracer(tmp_path / "t"))
        orch.planner = _StreamingFakePlanner([
            ["press #1", "press #1", "press #1"],
        ])
        outcome = await orch._planner_loop("make a new note", {
            "decisions": []})
        return outcome, server, orch

    outcome, server, orch = asyncio.run(go())
    assert outcome == "awaiting_user"
    assert server.said[-1] == "I'm stuck on that, can you help?"
    assert len([1 for method, params in server.rpcs
                if method == "act" and params.get("op") == "press"]) == 4
