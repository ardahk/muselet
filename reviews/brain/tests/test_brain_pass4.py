"""brain-13: stale speculative routes queue ahead of the final route on the FIFO MLX worker."""
import time, re
import pytest
from brain.planner import MLXWorker

ROUTE_S = 0.08  # stand-in for one route forward pass


def fake_route(text, ctx):
    time.sleep(ROUTE_S)
    return text


def test_brain13_final_route_waits_behind_stale_partials():
    w = MLXWorker()
    partials = ["set", "set the", "set the volume", "set the volume to",
                "set the volume to thirty", "set the volume to thirty percent"]
    for p in partials:                      # what _speculative_route does
        w.submit(fake_route, p, {})
    t = time.perf_counter()
    w.submit(fake_route, "Set the volume to thirty percent.", {}).result()
    waited = time.perf_counter() - t
    # final (punctuated -> spec miss) should cost ~1 route, not 7
    assert waited < 2 * ROUTE_S, f"final route waited {waited*1000:.0f} ms"


def test_brain13_final_punctuation_misses_spec_key():
    norm = lambda s: re.sub(r"\s+", " ", s.strip().lower())  # orchestrator._engine_route
    assert norm("Set the volume to thirty percent.") == norm("set the volume to thirty percent")
