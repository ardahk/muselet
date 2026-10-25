"""Deterministic exact answers (task 3): no model call when code parses;
the Calculator app path types the expression and reads the display back."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from brain import calc
from brain.orchestrator import Orchestrator
from fakes import CapturingTracer, FakeEngine, FakeServer

CASES = [
    # percentages
    ("15 percent of 80", "15% of 80 is 12"),
    ("what's 15% of 80", "15% of 80 is 12"),
    ("what is twenty percent of fifty", "20% of 50 is 10"),
    ("what's 18% tip on 64.50", "An 18% tip on $64.50 is $11.61, total $76.11"),
    ("what's an 18 percent tip on sixty four fifty",
     "An 18% tip on $64.50 is $11.61, total $76.11"),
    ("what's a 20% tip on $45", "A 20% tip on $45 is $9, total $54"),
    ("what's 20% off $50", "20% off $50 is $40"),
    ("what percent of 80 is 12", "12 is 15% of 80"),
    ("12 is what percent of 80", "12 is 15% of 80"),
    ("what is half of 80", "half of 80 is 40"),
    # arithmetic in digits and words
    ("2+2", "2 plus 2 is 4"),
    ("what is 7 x 8", "7 times 8 is 56"),
    ("What is twelve times seven?", "12 times 7 is 84"),
    ("one hundred and twenty three plus four", "123 plus 4 is 127"),
    ("sixty-four point five divided by two", "64.5 divided by 2 is 32.25"),
    ("what's 1,250 times 3", "1,250 times 3 is 3,750"),
    ("what is 2 to the power of 10", "2 to the power of 10 is 1,024"),
    ("square root of 144", "The square root of 144 is 12"),
    ("what is 10 divided by 0", "You can't divide by zero"),
    # conversions
    ("convert 5 pounds to kilograms", "5 lb is 2.27 kg"),
    ("how many grams in 3 ounces", "3 oz is 85.05 g"),
    ("what's 70 F in celsius", "70°F is 21.1°C"),
    ("100 c to f", "100°C is 212°F"),
    ("10 km in miles", "10 km is 6.21 mi"),
    ("how many ml in a cup", "1 cup is 236.59 ml"),
    ("three tablespoons to ml", "3 tbsp is 44.36 ml"),
    ("5 feet 10 inches in cm", "5 ft 10 in is 177.8 cm"),
]


@pytest.mark.parametrize("q,want", CASES)
def test_exact_answers(q, want):
    assert calc.answer(q) == want


@pytest.mark.parametrize("q", [
    "set volume to 30", "open safari", "what is the capital of France",
    "what time is it", "tell me a joke", "", "two thousand twenty six minus "
    "nineteen ninety", "remind me in 5 minutes", "who won the game"])
def test_non_math_falls_back(q):
    assert calc.answer(q) is None


@pytest.mark.parametrize("v,src,dst,want", [
    (1, "kg", "lb", 2.2046), (1, "mi", "km", 1.6093), (1, "m", "ft", 3.2808),
    (1, "in", "cm", 2.54), (1, "oz", "g", 28.3495), (1, "cups", "ml", 236.588),
    (1, "tbsp", "ml", 14.7868), (32, "F", "C", 0.0), (-40, "C", "F", -40.0),
])
def test_convert_factors(v, src, dst, want):
    r = calc.convert(v, src, dst)
    assert r is not None and abs(r[0] - want) < 1e-3


def test_convert_incompatible_units():
    assert calc.convert(1, "kg", "km") is None


@pytest.mark.parametrize("text,want", [
    ("twenty one", "21"), ("one hundred and five", "105"),
    ("three thousand two hundred", "3200"), ("seven point five", "7.5"),
])
def test_spoken_numbers(text, want):
    assert calc.normalize(text)[0].strip() == want


# ---------- Calculator app path (hobby gaps) ----------

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
    tracer = CapturingTracer(tmp_path / "traces")
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
