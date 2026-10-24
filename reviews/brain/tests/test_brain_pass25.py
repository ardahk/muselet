"""brain pass 25 repro (wip/local 0db1681): GenericMLXDecider init handshake shares the job queue with the worker."""
import sys
import threading
import types


def test_brain26_generic_decider_init_does_not_hang(monkeypatch):
    """The worker puts its init result on self._jobs and then immediately blocks on self._jobs.get(); it usually
    takes its own `None` back, treats it as the shutdown sentinel and exits, leaving __init__ blocked forever."""
    from brain import generic_decide as gd

    mx = types.ModuleType("mlx.core")
    mlx = types.ModuleType("mlx"); mlx.core = mx
    lm = types.ModuleType("mlx_lm"); lm.load = lambda p: (object(), None)
    models = types.ModuleType("mlx_lm.models"); cache = types.ModuleType("mlx_lm.models.cache")
    cache.make_prompt_cache = lambda m: []
    for k, v in {"mlx": mlx, "mlx.core": mx, "mlx_lm": lm, "mlx_lm.models": models,
                 "mlx_lm.models.cache": cache}.items():
        monkeypatch.setitem(sys.modules, k, v)
    monkeypatch.setattr(gd, "split_model", lambda m: (None, None))
    monkeypatch.setattr(gd, "GenericRenderer", lambda p: types.SimpleNamespace(static_tokens=[1]))
    monkeypatch.setattr(gd.GenericMLXDecider, "_prefill", lambda self, t: [])

    hung = 0
    for _ in range(20):
        box = {}
        t = threading.Thread(target=lambda: box.setdefault("d", gd.GenericMLXDecider("x")), daemon=True)
        t.start(); t.join(2.0)
        hung += t.is_alive()
    assert hung == 0, f"__init__ hung in {hung}/20 constructions"
