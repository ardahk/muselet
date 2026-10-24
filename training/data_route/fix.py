"""Step 1b: full-pool re-judge of the labels with audit noise >= 13% or named weak by the lead (rule R3).
Same protocol as the audit: two blind judges; rows where either disagrees with gold or with the other go to the
adjudicator. Audited rows are skipped (they already carry an adjudicated verdict).

  python training/data_route/fix.py judge|adjudicate
"""

from __future__ import annotations

import json
import sys

from audit import (ADJUDICATE, ADJUDICATOR, JUDGES, ROUTE_JUDGE, _batched, _rl, _route_lines)
from common import DATA, ctx_line, jdump, jload, load_it2b, option_block, parse_json, spend  # noqa: F401
from policy import POLICY

F = DATA / "fix"
R3_LABELS = ("compose_email", "web_search", "open_folder", "wifi", "media_control", "copy_selection", "set_volume",
             "sleep_display", "set_brightness", "create_event")


def judge() -> None:
    items = jload(F / "judged.jsonl")
    if not items:
        route, _ = load_it2b()
        audited = {x["idx"] for x in jload(DATA / "audit" / "sample.jsonl")}
        items = [{"idx": i, "utterance": r["utterance"], "context": r["context"], "gold": r["label"]}
                 for i, r in enumerate(route) if r["label"] in R3_LABELS and i not in audited]
        for x in items:  # R1 is applied before judging so offline web rows are judged with their fixed context
            if x["gold"] in ("web_search", "open_url") and x["context"].get("online") is False:
                x["context"] = {**x["context"], "online": True}
    opts = option_block()
    for m in JUDGES:
        _batched(items, f"r:{m}", m, lambda s: ROUTE_JUDGE.format(options=opts, policy=POLICY, items=_route_lines(s)),
                 "label", "fix_route", batches=(25, 5, 1))
        jdump(F / "judged.jsonl", items)
    print(json.dumps({"n": len(items), "spend": spend()}))


def adjudicate() -> None:
    items = jload(F / "judged.jsonl")
    opts = option_block()
    need = [x for x in items if not (_rl(x, JUDGES[0]) == _rl(x, JUDGES[1]) == x["gold"]) and not x.get("r:adj")]

    def rp(sub):
        blocks = []
        for k, x in enumerate(sub):
            j = [f'judge {n + 1}: {_rl(x, m)} ({(x.get(f"r:{m}") or {}).get("why", "")})' for n, m in enumerate(JUDGES)]
            blocks.append(f'Item {k}. Context: {ctx_line(x["context"])}\nRequest: "{x["utterance"]}"\n'
                          f'Gold: {x["gold"]}\n' + "\n".join(j))
        return ADJUDICATE.format(options=opts, policy=POLICY, items="\n\n".join(blocks))
    # 1,555 rows: low reasoning effort and larger batches keep the full-pool pass inside the $80 budget
    import audit
    orig = audit.call
    audit.call = lambda m, p, st: orig(m, p, st, effort="low")
    _batched(need, "r:adj", ADJUDICATOR, rp, "label", "fix_route_adj", batches=(20, 4, 1))
    jdump(F / "judged.jsonl", items)
    print(json.dumps({"adjudicated": len(need), "spend": spend()}))


if __name__ == "__main__":
    {"judge": judge, "adjudicate": adjudicate}[sys.argv[1]]()
