import asyncio, json, sys
import tinker
from muselet_train import datums as D
import muselet_train.train as T
from muselet_train.train import evaluate, OUT
_rm = T.route_metrics
T.route_metrics = lambda rows: _rm(rows) if rows else {}
from muselet_train.route_render import STUDENT_MODEL
name, path = sys.argv[1], sys.argv[2]
items = D.route_items("v3m", ())
split_of = {it.utterance: it.split for it in items}
va = [r for r in D.args_rows("v3m", split_of) if r["split"] == "val"]
sc = tinker.ServiceClient()
cl = sc.create_sampling_client(base_model=path[5:]) if path.startswith("base:") else sc.create_sampling_client(model_path=path)
new = {"draft_email", "compose_text"}
async def go():
    a = await evaluate(cl, [], [r for r in va if r["skill"] not in new], STUDENT_MODEL)
    b = await evaluate(cl, [], [r for r in va if r["skill"] in new], STUDENT_MODEL)
    return a, b
a, b = asyncio.run(go())
keys = ("args_em", "args_em_runtime", "args_empty_runtime", "args_n")
res = {"v2_skills": {k: a[k] for k in keys}, "new_skills": {k: b[k] for k in keys}}
(OUT / name).mkdir(parents=True, exist_ok=True)
(OUT / name / "eval_args_val3.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res))
