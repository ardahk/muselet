import asyncio
import ast
import copy
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from brain import calc
from brain.orchestrator import Orchestrator
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


class _CapturingTracer(Tracer):
    def finish(self, outcome):
        self.last = copy.deepcopy(self.current)
        super().finish(outcome)


UNHANDLED_R4_CALC = {
    "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15",
    "C17", "C20", "C22", "C23", "C24", "C25", "C26", "C27", "C28",
    "C29", "C30",
}


def _orchestrator(tmp_path, display="15", engine=None, act=None):
    server = FakeServer(act=act or (lambda p: (
        {"ok": True, "output": display} if p["op"] == "script"
        else {"ok": True, "epoch": 2}
    )))
    tracer = _CapturingTracer(tmp_path / "traces")
    return Orchestrator(server, tracer=tracer, engine=engine), server, tracer


def _act_params(server):
    return [params for method, params in server.rpcs if method == "act"]


def test_calc_result_preserves_answer_and_expression():
    parsed = calc.result("what's 11 plus 4 on the calculator")
    assert parsed is not None
    assert parsed.value == 15
    assert parsed.expr == "11+4"
    assert parsed.answer == calc.answer("11 plus 4")
    assert calc.result("1 divided by 0").value is None


def test_calculator_path_types_expression_and_reads_display(tmp_path):
    async def scenario():
        orch, server, tracer = _orchestrator(tmp_path)
        outcome = await orch.handle_utterance("11 plus 4", {"app": "Calculator"})
        acts = _act_params(server)
        assert outcome["outcome"] == "ok"
        assert [(a["op"], a.get("app"), a.get("combo")) for a in acts[:3]] == [
            ("open", "Calculator", None), ("keys", None, "esc"),
            ("keys", None, "1"),
        ]
        assert [a["combo"] for a in acts if a["op"] == "keys"][1:] == [
            "1", "1", "shift+=", "4", "="]
        readbacks = [a for a in acts if a["op"] == "script"]
        assert len(readbacks) == 1
        assert readbacks[0]["lang"] == "jxa"
        assert "function run()" in readbacks[0]["code"]
        assert not server.confirms
        assert tracer.last["decisions"][-1]["calc_target"] == "calculator"
        assert tracer.last["calc_readback"] == "15"
        assert tracer.last["release_to_first_action_ms"] is not None
    asyncio.run(scenario())


def test_calculator_path_enters_percent_and_negative_conversion_digits(tmp_path):
    async def scenario():
        orch, server, _ = _orchestrator(tmp_path, display="12")
        await orch.handle_utterance("what's 15% of 80 on the calculator")
        assert [a["combo"] for a in _act_params(server)
                if a["op"] == "keys"][1:] == ["1", "2", "="]

        negative, negative_server, _ = _orchestrator(tmp_path / "negative", display="-17.8")
        await negative.handle_utterance(
            "0 fahrenheit to celsius on the calculator")
        assert [a["combo"] for a in _act_params(negative_server)
                if a["op"] == "keys"][1:] == [
            "0", "-", "1", "7", ".", "8", "="
        ]
    asyncio.run(scenario())


def test_calculator_mismatch_fails_but_says_answer_without_asking(tmp_path):
    async def scenario():
        orch, server, tracer = _orchestrator(tmp_path, display="99")
        outcome = await orch.handle_utterance("11 plus 4", {"app": "Calculator"})
        assert outcome["outcome"] == "failed"
        assert server.said[-1] == calc.result("11 plus 4").answer
        assert not server.confirms
        assert tracer.last["decisions"][-1]["calc_target"] == "calculator"
    asyncio.run(scenario())


@pytest.mark.parametrize("opened", [
    {"ok": False, "error": "activation failed"},
    {"ok": True, "expect_ok": False},
    {"ok": True, "app": "TextEdit"},
    {"ok": True, "diff_text": 'app: TextEdit | window: "Notes.rtf"'},
    {"ok": True, "expect_ok": True, "diff_text": 'app: TextEdit | window: "Notes.rtf"'},
])
def test_brain25_calculator_keys_gated_on_calculator_frontmost(tmp_path, opened):
    async def scenario():
        orch, server, _ = _orchestrator(tmp_path, act=lambda p: opened)
        outcome = await orch.handle_utterance("11 plus 4 on the calculator")
        assert outcome["outcome"] == "failed"
        assert _act_params(server) == [{"op": "open", "app": "Calculator",
                                       "expect": 'app "Calculator"'}]
    asyncio.run(scenario())


def test_calculator_open_verified_before_keys(tmp_path):
    def act(params):
        if params["op"] == "open":
            return {"ok": True, "expect_ok": True, "app": "Calculator",
                    "diff_text": 'app: Calculator | window: "Calculator"'}
        return {"ok": True, "output": "15"}

    async def scenario():
        orch, server, _ = _orchestrator(tmp_path, act=act)
        assert (await orch.handle_utterance("11 plus 4 on the calculator"))["outcome"] == "ok"
        assert any(a["op"] == "keys" for a in _act_params(server))
    asyncio.run(scenario())


def test_notes_arithmetic_remains_bubble_only(tmp_path):
    async def scenario():
        orch, server, tracer = _orchestrator(tmp_path)
        outcome = await orch.handle_utterance("11 plus 4", {"app": "Notes"})
        assert outcome["outcome"] == "ok"
        assert not server.rpcs
        assert server.said == [calc.result("11 plus 4").answer]
        assert tracer.last["decisions"][-1]["calc_target"] == "bubble"
    asyncio.run(scenario())


def test_notes_arithmetic_still_uses_engine_route(tmp_path):
    async def scenario():
        engine = FakeEngine(default=("ANSWER", 0.99))
        orch, _, tracer = _orchestrator(tmp_path, engine=engine)
        result = await orch.handle_utterance("11 plus 4", {"app": "Notes"})
        assert result["outcome"] == "ok"
        assert engine.route_calls == ["11 plus 4"]
        assert tracer.last["decisions"][-1]["calc_target"] == "bubble"
    asyncio.run(scenario())


def test_frozen_r4_calculations_match_or_are_explicitly_unhandled(tmp_path):
    path = Path(__file__).parents[2] / "bench/hobbylm/upstream/data/frozen/hobbymac-sealed-test-r4.tsv"
    mismatches = set()
    unhandled = set()
    rows = [line.split("\t", 3) for line in path.read_text().splitlines() if line]
    calc_rows = [row for row in rows if row[1] == "calc"]
    assert len(calc_rows) == 30
    for ident, _, text, expected in calc_rows:
        try:
            expected_value = float(expected.replace(",", ""))
            parsed = calc.result(text)
            if parsed is None or parsed.value is None:
                unhandled.add(ident)
                continue
            assert abs(parsed.value - expected_value) <= 1e-9

            async def scenario():
                orch, _, tracer = _orchestrator(
                    tmp_path / ident, display=expected.strip())
                outcome = await orch.handle_utterance(text, {"app": "Calculator"})
                return outcome, tracer.last

            outcome, trace = asyncio.run(scenario())
            assert outcome["outcome"] == "ok"
            assert trace["decisions"][-1]["calc_target"] == "calculator"
        except Exception as exc:
            mismatches.add(f"{ident} {text!r} expected {expected!r}: {exc}")
    assert unhandled == UNHANDLED_R4_CALC
    assert not mismatches, "\n".join(sorted(mismatches))


def test_calc_answer_matches_origin_main_for_frozen_utterances():
    test_path = Path(__file__).with_name("test_calc.py")
    tree = ast.parse(test_path.read_text())
    cases = next(ast.literal_eval(node.value) for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "CASES"
                         for target in node.targets))
    utterances = [case[0] for case in cases]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            try:
                parameter = ast.literal_eval(node.args[0])
            except (ValueError, TypeError):
                continue
            if parameter == "q":
                try:
                    utterances.extend(ast.literal_eval(node.args[1]))
                except (ValueError, TypeError):
                    pass
            elif parameter == "text,want":
                utterances.extend(row[0] for row in ast.literal_eval(node.args[1]))
    rows = [line.split("\t", 3) for line in (
        Path(__file__).parents[2] / "bench/hobbylm/upstream/data/frozen/"
        "hobbymac-sealed-test-r4.tsv").read_text().splitlines() if line]
    utterances.extend(row[2] for row in rows if row[1] == "calc")
    source = subprocess.check_output(
        ["git", "show", "origin/main:ml/src/brain/calc.py"], text=True)
    baseline = types.ModuleType("origin_calc")
    sys.modules[baseline.__name__] = baseline
    exec(compile(source, "origin/main:ml/src/brain/calc.py", "exec"),
         baseline.__dict__)
    for text in dict.fromkeys(utterances):
        assert calc.answer(text) == baseline.answer(text), text


def test_calculator_script_is_valid_javascript_and_number_is_fixed():
    code = Orchestrator._calculator_readback_script()
    assert "function run()" in code
    node = shutil.which("node")
    if node:
        result = subprocess.run([node, "--check"], input=code, text=True,
                                capture_output=True)
        assert result.returncode == 0, result.stderr
    assert Orchestrator._calculator_number(1e14) == "100000000000000"
    assert Orchestrator._calculator_number(1 / 3) == "0.333333333333"


def test_jxa_script_confirmation_matches_origin_main_examples(tmp_path):
    orch, _, _ = _orchestrator(tmp_path)
    assignment = (
        'var x = Application("System Events").processes.byName("Calculator")'
        '.windows[0]; x.value = "1";'
    )
    assert orch.script_needs_confirm("jxa", assignment) is True
    assert orch.script_needs_confirm(
        "jxa", Orchestrator._calculator_readback_script()) is True


def test_rejected_brightness_delta_fails_without_asking(tmp_path):
    async def scenario():
        class RejectingServer(FakeServer):
            async def rpc(self, method, params, timeout=30):
                self.rpcs.append((method, params))
                if method == "skill":
                    return {"ok": False, "error": "delta unsupported"}
                return {"ok": True}

        rejecting = RejectingServer()
        trace = Tracer(tmp_path / "reject")
        failed = Orchestrator(rejecting, tracer=trace,
                              engine=FakeEngine(default=("set_brightness", .99)))
        result = await failed.handle_utterance("make the screen brighter")
        assert result["outcome"] == "failed"
        skill = next(params for method, params in rejecting.rpcs
                     if method == "skill")
        assert skill == {"name": "set_brightness", "args": {"delta": 10}}
        assert rejecting.said
        assert not any("ask" in line.casefold() for line in rejecting.said)
        assert not rejecting.confirms
    asyncio.run(scenario())
