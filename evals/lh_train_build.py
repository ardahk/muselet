"""Build evals/lh_train.jsonl: TRAINING-ONLY live tasks on the fixture sites (teacher/student trajectory
collection). Never report these as eval numbers. Run: python3 evals/lh_train_build.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench.fixtures.train_tasks import TRAIN_TASKS  # noqa: E402
from evals.lh_v1_build import FIX, milestones, web_case  # noqa: E402

NAMES = {"cart": ["cart_ok", "no_order"], "order": ["order_placed", "items_ok", "name_ok", "address_ok"],
         "quiz": ["answered", "correct"]}


def build(task):
    exp = task["expect"]
    kind = next(k for k in ("cart", "cart_group", "order", "sent", "quiz") if k in exp)
    if kind == "sent":
        names = ["sent_one", "to_ok"] + [n for k, n in (("in_reply_to", "thread_ok"), ("forward_of", "forward_ok"),
                                                       ("subject_has", "subject_ok"), ("body_has", "body_ok"))
                                         if k in exp["sent"]]
        if "body_any" in exp["sent"] and "body_ok" not in names:
            names.append("body_ok")
    elif kind == "cart_group":
        names = [f"{g}_qty" for g in exp["cart_group"]] + ["no_extras", "no_order"]
    else:
        names = NAMES[kind]
    case = web_case(task["id"], "train-" + task["id"].split("-")[1], task["start"], task["utterance"], names,
                    require_confirm=kind in ("order", "sent"))
    case["suite"] = "lh-train-1.0"
    case["tier"] = "TRAIN"
    if task["preset"]:
        case["setup"][0] = {"shell": f"curl -sf -X POST '{FIX}/api/reset?case={task['id']}&preset={task['preset']}'"}
    case["milestones"] = milestones(task["id"], names)
    return case


if __name__ == "__main__":
    out = Path(__file__).with_name("lh_train.jsonl")
    cases = [build(t) for t in TRAIN_TASKS]
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
    print(f"wrote {len(cases)} training cases to {out}")
