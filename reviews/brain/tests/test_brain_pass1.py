"""Failing tests for brain-lane findings (pass 1). Run from a wip/local checkout:
    PYTHONPATH=ml/src pytest -q reviews/brain/tests/test_brain_pass1.py
brain1/brain2 are regressions (fixed at bcd3b75); brain3-5 fail at bcd3b75 logic."""
import asyncio
import time

import pytest

from brain.catalog import Catalog
from brain import decision as D


def _engine():
    eng = D.DecisionEngine.__new__(D.DecisionEngine)
    eng.catalog = Catalog.load()
    eng.last_action = "none"
    rr = D.RouteRenderer.__new__(D.RouteRenderer)   # no tokenizer needed
    rr._options = D.catalog_options(eng.catalog)
    eng.rr = rr

    class _P:
        value = True
    eng._probe = _P()
    return eng


def test_brain1_special_descriptions_come_from_catalog():
    eng = _engine()
    got = dict(eng.options()[-4:])
    want = {o["name"]: o["description"] for o in eng.catalog.special_options}
    assert got == want


def test_brain1_last_action_none_renders_lowercase_none():
    eng = _engine()
    d = eng._route_decision("x", {"app": "Finder", "focused": "none",
                                  "selection": False, "last_action": None})
    assert "last_action=none" in d.text


def test_brain2_arg_signature_matches_training():
    eng = _engine()
    # training/src/muselet_train/catalog.py:arg_signature on cloud/data-pipeline
    assert eng.arg_signature("find_file") == \
        "query:string required, kind:enum any|pdf|image|video|document|folder optional"
    assert eng.arg_signature("set_volume") == "level:int 0-100 required"


@pytest.mark.parametrize("text,sec", [
    ("twenty five minutes", 1500), ("forty-five minutes", 2700),
    ("1 hour and a half", 5400)])
def test_brain3_duration_compound_numbers(text, sec):
    assert D.parse_duration(text) in (sec, None)   # wrong value is worse than ASK


@pytest.mark.parametrize("text,hour", [("tomorrow at 9", 9), ("at 3", None),
                                       ("friday at 3", None)])
def test_brain3_datetime_never_silently_wrong(text, hour):
    iso = D.parse_datetime(text)
    if iso is None:
        return
    from datetime import datetime
    dt = datetime.fromisoformat(iso)
    assert (dt - datetime.now()).days < 8, f"{text!r} -> {iso} (months away)"
    if hour is not None:
        assert dt.hour == hour, f"{text!r} -> {iso}"


class _Tok:
    """'a','c','g','w' merge into the prefix like the real Qwen3.5 tokenizer."""
    def encode(self, s, add_special_tokens=False):
        if s.startswith("choice#") and s[7:] in ("a", "c", "g", "w"):
            return [1, 2]
        return [ord(c) for c in s]

    def decode(self, t):
        return "".join(chr(x) for x in t)


class _R:
    tokenizer = _Tok()


def test_brain4_37th_option_gets_id_b_not_crash():
    cr = D.AlphaChoiceRenderer(_R())
    labels = [f"opt{i}" for i in range(37)]
    r = cr.render_choices(labels)        # ConfigurationError today ('a')
    assert r.label_tokens["opt36"] == ord("b")


def test_brain5_engine_does_not_block_event_loop():
    from brain.orchestrator import Orchestrator

    class Eng:
        last_action = "none"
        def route(self, text, ctx):
            time.sleep(0.5)               # stands in for an MLX forward pass
            return D.RouteResult(probs={"ANSWER": 1.0, "ASK": 0.0},
                                 top="ANSWER", p_top=1.0, ms={})

    class Srv:
        async def ui(self, *a, **k): pass
        async def say(self, *a, **k): pass

    async def main():
        orch = Orchestrator(Srv(), Catalog.load(), engine=Eng())
        lag = []
        async def ticker():
            for _ in range(10):
                t = time.perf_counter(); await asyncio.sleep(0.02)
                lag.append(time.perf_counter() - t)
        tk = asyncio.create_task(ticker())
        await asyncio.sleep(0.03)          # ticker is now mid-sleep
        await orch.handle_utterance("what is 2+2")
        await tk
        return max(lag)
    assert asyncio.run(main()) < 0.2, "receive loop starved while the model runs"


# ---------------- pass 3 ----------------

def _orch():
    from brain.orchestrator import Orchestrator
    o = Orchestrator.__new__(Orchestrator)
    o.catalog = Catalog.load()
    return o


@pytest.mark.parametrize("code", [
    'tell application "Safari" to get (do JavaScript '
    '"document.querySelector(\'#place-order\').click()" in document 1)',
    'tell application "System Events" to tell process "Safari"\n'
    'get name of window 1\nclick button "Place Order" of window 1\nend tell',
    'tell application "System Events" to tell process "Finder" to get '
    '(perform action "AXPress" of button "Empty" of window 1)',
    'tell application "Finder" to open file "x.command" of desktop',
])
def test_brain9_side_effect_scripts_need_confirm(code):
    assert _orch().script_needs_confirm("applescript", code)


@pytest.mark.parametrize("utt,on", [
    ("turn the sound back on", False),     # unmute
    ("turn the sound off", True),          # mute
    ("unmute, I'm on a call", False),
])
def test_brain10_mute_polarity(utt, on):
    assert _orch()._coerce_args("mute", {"on": on}, utterance=utt)["on"] is on
