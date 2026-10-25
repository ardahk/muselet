"""decisions-40 repro: count gold single-skill routes that open_ended_redirect sends to the planner.
Usage: git archive origin/cloud/open-ended ml/src/brain/app_hints.py prompts/app_hints.jsonl skills/catalog.json evals/route_v1_clean.jsonl evals/route_v2.jsonl | tar -x -C /tmp/oe && cd /tmp/oe && python3 <this>"""
import json, sys
sys.path.insert(0, "ml/src/brain")
import app_hints as ah
cat = json.load(open("skills/catalog.json"))
skills = cat["skills"] if isinstance(cat, dict) and "skills" in cat else cat
risk = {s["name"]: s.get("risk") for s in skills}
for f in ["evals/route_v1_clean.jsonl", "evals/route_v2.jsonl"]:
    rows = [json.loads(l) for l in open(f)]
    flips = [(r["label"], r["utterance"], h.id) for r in rows
             if (h := ah.open_ended_redirect(r["label"], r["utterance"], risk.get(r["label"]))) is not None]
    print(f, len(rows), "flipped:", len(flips))
    for x in flips[:8]:
        print("  ", x)
