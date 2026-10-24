"""Partial-utterance speculation step 2: route + ARGS ahead (task 5)."""

import asyncio
import threading

import pytest
from brain.catalog import Catalog
from brain.orchestrator import Orchestrator
from brain.planner import worker
from brain.traces import Tracer
from fakes import FakeEngine, FakeServer


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tracer(tmp_path):
    return Tracer(tmp_path / "traces")


def _drain():
    worker().submit(lambda: None).result(5)


def _eng():
    return FakeEngine(
        {"open saf": ("open_app", 0.7), "open safari": ("open_app", 0.96),
         "open safari now": ("open_app", 0.96), "mute": ("mute", 0.4),
         "lock the screen": ("lock_screen", 0.97)},
        {("open_app", "open safari"): {"app": "Safari"},
         ("open_app", "open saf"): {"app": "Saf"},
         ("open_app", "open safari now"): {"app": "Safari"}})


def test_confident_partial_speculates_args_and_final_reuses(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("Open  Safari")
    _drain()
    assert eng.args_calls == [("open_app", "Open  Safari")]
    run(o.handle_utterance("open safari"))
    assert eng.route_calls == ["Open  Safari"]          # no route on final
    assert eng.args_calls == [("open_app", "Open  Safari")]   # no ARGS either
    assert o.server.skills() == [{"name": "open_app", "args": {"app": "Safari"}}]
    d = tracer.dir.glob("*.jsonl")
    assert '"spec_args": true' in next(d).read_text()


def test_changed_partial_ignores_stale_args(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    gate = threading.Event()
    eng.gate = gate                    # the first route blocks on the worker
    o._speculative_route("open saf")
    o._speculative_route("open safari")
    gate.set()
    _drain()
    # the stale job saw a newer partial and skipped its ARGS
    assert eng.args_calls == [("open_app", "open safari")]
    run(o.handle_utterance("open safari"))
    assert o.server.skills()[0]["args"] == {"app": "Safari"}
    assert eng.route_calls[-1] == "open safari" and len(eng.route_calls) <= 2


def test_stale_partials_skip_before_running(tracer):
    """brain-13: queued superseded partials never run a forward pass, so the
    final route waits behind at most one in-flight job."""
    from brain.planner import worker
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    gate = threading.Event()
    worker().submit(gate.wait)         # worker busy: partials queue up
    for p in ("open", "open sa", "open saf", "open safari"):
        o._speculative_route(p)
    gate.set()
    _drain()
    assert eng.route_calls == ["open safari"]
    run(o.handle_utterance("Open Safari."))    # punctuation/case: still a hit
    assert eng.route_calls == ["open safari"]
    assert o.server.skills()[0]["args"] == {"app": "Safari"}


def test_final_differs_from_partial_routes_fresh(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("open safari")
    _drain()
    run(o.handle_utterance("open safari now"))
    assert eng.route_calls == ["open safari", "open safari now"]
    assert eng.args_calls[-1] == ("open_app", "open safari now")


def test_unconfident_partial_routes_only(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("open saf")          # p_top 0.7 >= tau 0.55 -> args
    _drain()
    o.tau = 0.8
    o._speculative_route("mute")              # 0.4 < tau: route only
    _drain()
    assert eng.args_calls == [("open_app", "open saf")]


def test_argless_skill_route_only(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("lock the screen")
    _drain()
    assert eng.args_calls == []
    run(o.handle_utterance("lock the screen"))
    assert o.server.skills() == [{"name": "lock_screen", "args": {}}]
    assert eng.route_calls == ["lock the screen"]


def test_same_partial_twice_submits_once(tracer):
    eng = _eng()
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("open safari")
    o._speculative_route("open safari ")
    _drain()
    assert eng.route_calls == ["open safari"]


def test_partial_ctx_used_for_speculation(tracer):
    seen = []
    eng = _eng()
    orig = eng.route
    eng.route = lambda t, c: (seen.append(c["app"]), orig(t, c))[1]
    o = Orchestrator(FakeServer(), Catalog.load(), tracer, engine=eng)
    o._speculative_route("open safari", {"app": "Notes"})
    _drain()
    assert seen == ["Notes"]
