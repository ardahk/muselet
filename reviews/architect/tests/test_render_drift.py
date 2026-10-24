"""architect-2: runtime router prompt must match the training renderer.
Run from a wip/local checkout: uv run --project ml python reviews/architect/tests/test_render_drift.py
(stubs mlx so it runs on Linux)."""
import json, sys, types
for m in ["mlx", "mlx.core", "mlx_lm"]:
    sys.modules[m] = types.ModuleType(m)
sys.modules["mlx"].core = sys.modules["mlx.core"]
from brain.decision import DecisionEngine
from brain.catalog import Catalog

class F: catalog = Catalog.load()
rt = dict(DecisionEngine.options(F()))
cat = {o["name"]: o["description"] for o in json.load(open("skills/catalog.json"))["special_options"]}
bad = [k for k in cat if rt[k] != cat[k]]
sig = DecisionEngine.arg_signature(F(), "find_file")
want = "query:string required, kind:enum any|pdf|image|video|document|folder optional"  # training/src/muselet_train/catalog.py _arg_sig
print("special mismatches:", bad); print("runtime sig:", sig); print("train sig:  ", want)
assert not bad and sig == want
