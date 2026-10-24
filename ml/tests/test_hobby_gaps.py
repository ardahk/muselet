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
from brain.catalog import Catalog, CatalogError
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


def _skill_engine(label, args=None):
    return FakeEngine(default=(label, 0.99), argmap={
        (label, "brightness to 70"): {**(args or {}), "level": 70},
    })


@pytest.mark.parametrize(("text", "label", "expected"), [
    ("make the screen brighter", "set_brightness", {"delta": 15}),
    ("make the screen dimmer", "set_brightness", {"delta": -15}),
    ("volume up", "change_volume", {"delta": 10}),
    ("turn it down a lot", "change_volume", {"delta": -25}),
])
def test_relative_brightness_and_volume_inference(tmp_path, text, label, expected):
    async def scenario():
        orch, server, _ = _orchestrator(
            tmp_path, engine=_skill_engine(label))
        await orch.handle_utterance(text)
        assert server.skills()[0] == {"name": label, "args": expected}
    asyncio.run(scenario())


def test_absolute_brightness_and_direct_failure_bubble(tmp_path):
    async def scenario():
        orch, server, _ = _orchestrator(
            tmp_path, engine=_skill_engine("set_brightness"))
        await orch.handle_utterance("brightness to 70")
        assert server.skills()[0]["args"] == {"level": 70}

        class RejectingServer(FakeServer):
            async def rpc(self, method, params, timeout=30):
                self.rpcs.append((method, params))
                if method == "skill":
                    return {"ok": False, "error": "delta unsupported"}
                return {"ok": True}

        rejecting = RejectingServer()
        trace = Tracer(tmp_path / "reject")
        failed = Orchestrator(rejecting, tracer=trace,
                              engine=_skill_engine("set_brightness"))
        result = await failed.handle_utterance("make the screen brighter")
        assert result["outcome"] == "failed"
        assert rejecting.said
        assert not any("ask" in line.casefold() for line in rejecting.said)
        assert not rejecting.confirms
    asyncio.run(scenario())


def test_v0_relative_route_and_generic_require_one_of(tmp_path):
    orch, _, _ = _orchestrator(tmp_path)
    assert orch.route("make the screen brighter")["args"] == {"delta": 15}
    assert orch.route("turn it down a lot")["args"] == {"delta": -25}
    assert orch.route("look up the weather")["name"] == "web_search"
    assert orch.route("turn it up")["args"] == {"delta": 10}
    assert orch.route("volume down")["args"] == {"delta": -10}
    data = {"skills": [{
        "name": "set_brightness",
        "args": [
            {"name": "level", "type": "int", "required": False},
            {"name": "delta", "type": "int", "required": False},
        ],
        "require_one_of": ["level", "delta"],
    }]}
    catalog = Catalog(data)
    with pytest.raises(CatalogError):
        catalog.validate_args("set_brightness", {})
    assert catalog.validate_args("set_brightness", {"delta": 15}) == {"delta": 15}
    assert orch._missing("set_brightness", {}) == ["level"]


@pytest.mark.parametrize(("label", "args", "text", "want"), [
    ("set_brightness", {"level": 40}, "make it brighter", {"delta": 15}),
    ("change_volume", {"delta": 10}, "quieter", {"delta": -10}),
    ("set_volume", {"delta": 10}, "volume up", {"delta": 10}),
    ("change_volume", {}, "volume down", {"delta": -10}),
    ("set_brightness", {}, "turn brightness down a lot", {"delta": -15}),
])
def test_direction_override_replaces_model_arguments(tmp_path, label, args, text, want):
    async def scenario():
        engine = FakeEngine(default=(label, .99),
                            argmap={(label, text): args})
        orch, server, _ = _orchestrator(tmp_path, engine=engine)
        await orch.handle_utterance(text)
        assert server.skills()[0]["args"] == want
        assert not server.confirms
    asyncio.run(scenario())


def test_rel_delta_wins_for_volume_notches(tmp_path):
    async def scenario():
        engine = FakeEngine(default=("change_volume", .99))
        orch, server, tracer = _orchestrator(tmp_path, engine=engine)
        await orch.handle_utterance("turn the volume up two notches")
        assert server.skills()[0]["args"] == {"delta": 20}
        assert {"rel_delta": 20} in tracer.last["decisions"]
    asyncio.run(scenario())
