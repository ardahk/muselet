import asyncio
import copy
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
        assert tracer.last["decisions"][-1]["calc_target"] == "calculator"
        assert tracer.last["calc_readback"] == "15"
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


def test_all_frozen_r4_calculations_use_calculator_and_match_expected(tmp_path):
    path = Path(__file__).parents[2] / "bench/hobbylm/upstream/data/frozen/hobbymac-sealed-test-r4.tsv"
    mismatches = []
    rows = [line.split("\t", 3) for line in path.read_text().splitlines() if line]
    calc_rows = [row for row in rows if row[1] == "calc"]
    assert len(calc_rows) == 30
    for ident, _, text, expected in calc_rows:
        try:
            expected_value = float(expected.replace(",", ""))
            parsed = calc.result(text)
            assert parsed is not None and parsed.value is not None
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
            mismatches.append(f"{ident} {text!r} expected {expected!r}: {exc}")
    assert not mismatches, "\n".join(mismatches)


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
        assert rejecting.said[-1] == "I can't change brightness by steps yet"
        assert not rejecting.confirms
    asyncio.run(scenario())


def test_v0_relative_route_and_generic_require_one_of(tmp_path):
    orch, _, _ = _orchestrator(tmp_path)
    assert orch.route("make the screen brighter")["args"] == {"delta": 15}
    assert orch.route("turn it down a lot")["args"] == {"delta": -25}
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
