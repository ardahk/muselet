"""Upload the exact route / ARGS training items of a run as a private HF dataset (for multi-task iterations).

  python -m muselet_train.datums_export --run v2all --name main --repo jonsnov/muselet-route-datums-main \
      --teacher-files teacher_pilot_adj.jsonl teacher_ask_adj.jsonl teacher_v2_adj.jsonl
route.jsonl.gz: final RouteItems after the lead's label rules, with the rendered tokens the trainer used
(ASR noise applied to train items, as in training) and the soft target over choice ids.
args.jsonl.gz: ARGS chat messages (system/user/assistant); train on the last assistant message only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from huggingface_hub import HfApi

from muselet_train import datums as D
from muselet_train.catalog import REPO_ROOT, skill_by_name
from muselet_train.route_render import STUDENT_MODEL, RouteContext, args_messages, render_route

OUT = Path("/data/export/datums")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--teacher-files", nargs="*", default=[])
    ap.add_argument("--checkpoint", default="")
    ap.add_argument("--route-source", choices=["split", "dedup"], default="split",
                    help="dedup = the stale route_dedup.jsonl reader that the `main` run actually trained on")
    a = ap.parse_args()
    if a.route_source == "dedup":
        load = D._load
        D._load = lambda run, f: (load(run, "route_dedup.jsonl") if f == "route_train.jsonl"
                                  else [] if f == "route_val.jsonl" else load(run, f))
    assert a.repo.startswith("jonsnov/")
    stats, dropped = {}, set()
    items = D.route_items(a.run, tuple(a.teacher_files), stats=stats, dropped=dropped)
    split_of = {it.utterance: it.split for it in items}
    args = [r for r in D.args_rows(a.run, split_of) if r["utterance"] not in dropped]
    d = OUT / a.name
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / "route.jsonl.gz", "wt") as f:
        for it in items:
            text = D.noisy(it.utterance, "r:" + it.utterance, it.split)
            rend = render_route(RouteContext(**it.context), text)
            ids = dict(rend.label_tokens)
            f.write(json.dumps({"utterance": it.utterance, "rendered_utterance": text, "context": it.context,
                                "label": it.label, "split": it.split, "target": it.target,
                                "target_ids": {str(ids[k]): v for k, v in it.target.items()},
                                "tokens": rend.tokens, "choice_pos": rend.choice_pos}, ensure_ascii=False) + "\n")
    with gzip.open(d / "args.jsonl.gz", "wt") as f:
        for r in args:
            msgs = args_messages(skill_by_name(r["skill"]), RouteContext(**r["context"]), r["utterance"], r["target"])
            f.write(json.dumps({"skill": r["skill"], "utterance": r["utterance"], "context": r["context"],
                                "target": r["target"], "split": r["split"], "messages": msgs},
                               ensure_ascii=False) + "\n")
    cat = (REPO_ROOT / "skills" / "catalog.json").read_bytes()
    commit = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    meta = {"run": a.run, "name": a.name, "checkpoint": a.checkpoint, "student": STUDENT_MODEL,
            "catalog_version": json.loads(cat)["version"], "catalog_sha256": hashlib.sha256(cat).hexdigest(),
            "code_commit": commit, "route_source": a.route_source, "route": len(items), "args": len(args),
            "route_by_split": {s: sum(it.split == s for it in items) for s in ("train", "val")}, "label_stats":
            {k: dict(v) for k, v in stats.items()}}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    (d / "README.md").write_text(f"""# muselet route datums: {a.name}

- Renderer: `muselet_train.route_render.render_route` at commit `{commit}` (Qwen3.5-4B chat template, empty think
  block, assistant prefill `choice#`; byte-identical to `training/artifacts/route_render_samples.jsonl`).
- Route targets: soft labels over the 41 choice ids, read at `choice_pos` (the token after `choice#`). Tinker
  training sends them as sparse CSR (T, 41) targets with only the answer row nonzero (`datums._sparse`).
- Choice alphabet: `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789bdefhijklmnopqrstuvxyz` (a c g w dropped: not single tokens
  after `choice#`); catalog order, skill 37 = `b`, MULTI_STEP/ASK/REFUSE/ANSWER = `d e f h`.
- Catalog v{meta['catalog_version']} sha256 `{meta['catalog_sha256']}`.
- ARGS rows: chat messages, train on the last assistant message only. ASR noise is on route train items only.
""")
    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", private=True, exist_ok=True)
    info = api.upload_folder(folder_path=str(d), repo_id=a.repo, repo_type="dataset",
                             commit_message=f"route datums {a.name}")
    print(json.dumps({"repo": a.repo, "revision": info.oid, **{k: meta[k] for k in ("route", "args")}}))


if __name__ == "__main__":
    main()
