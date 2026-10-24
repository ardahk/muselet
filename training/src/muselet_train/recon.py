"""Phase 0 dataset recon: card/license, file inventory, parquet row counts (footers only),
schema and 3 raw examples from the smallest shard (or the head of a jsonl via HTTP range).
Writes /data/recon/<owner>__<name>.json for the markdown reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem, hf_hub_download

OUT = Path("/data/recon")
api, fs = HfApi(), HfFileSystem()


def trunc(v, n=600):
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + f"... <{len(v)} chars>"
    if isinstance(v, dict):
        if set(v) >= {"bytes"} and isinstance(v.get("bytes"), (bytes, bytearray)):
            return {"bytes": f"<{len(v['bytes'])} bytes>", "path": v.get("path")}
        return {k: trunc(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [trunc(x, n) for x in v[:8]] + ([f"... <{len(v)} items>"] if len(v) > 8 else [])
    return v


def jsonl_head(repo: str, path: str, k: int = 3, nbytes: int = 4_000_000):
    with fs.open(f"datasets/{repo}/{path}", "rb", block_size=nbytes) as f:
        buf = f.read(nbytes)
    lines = buf.split(b"\n")
    rows = []
    for ln in lines[:-1]:
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
        if len(rows) >= 50:
            break
    full = len(lines) - 1
    return rows, (nbytes / max(full, 1) if full else None)


def recon(repo: str, files: list[str] | None = None) -> dict:
    info = api.dataset_info(repo, files_metadata=True)
    sib = {s.rfilename: s.size or 0 for s in info.siblings}
    r = {"repo": repo, "sha": info.sha, "tags": info.tags, "gated": info.gated,
         "total_bytes": sum(sib.values()), "n_files": len(sib)}
    for doc in ("README.md", "LICENSE", "LICENSE.txt", "LICENSE.md"):
        if doc in sib:
            r[doc] = Path(hf_hub_download(repo, doc, repo_type="dataset")).read_text(errors="replace")[:20000]
    parquets = sorted(f for f in sib if f.endswith(".parquet"))
    if parquets:
        counts = {}
        for p in parquets:
            md = pq.ParquetFile(fs.open(f"datasets/{repo}/{p}")).metadata
            counts[p] = md.num_rows
        r["parquet_rows"] = counts
        target = files[0] if files else min((p for p in parquets if "test" not in p.split("/")[-1] or len(parquets) == 1), key=lambda p: sib[p], default=parquets[0])
        pf = pq.ParquetFile(fs.open(f"datasets/{repo}/{target}"))
        r["schema"] = str(pf.schema_arrow)
        t = pf.read_row_group(0)
        rows = t.slice(0, 50).to_pylist()
        r["sample_file"] = target
        r["rows"] = [trunc(x) for x in rows[:3]]
        r["rows_full_for_tokens"] = [trunc(x, 20000) for x in rows[:5]]
    else:
        js = files or sorted((f for f in sib if f.endswith((".jsonl", ".json"))), key=lambda f: sib[f])[:1]
        r["jsonl"] = {}
        for p in js:
            if p.endswith(".jsonl"):
                rows, bpr = jsonl_head(repo, p)
            else:
                with fs.open(f"datasets/{repo}/{p}", "rb") as f:
                    head = f.read(min(sib[p], 200_000_000))
                obj = json.loads(head)
                rows = obj if isinstance(obj, list) else [obj]
                bpr = sib[p] / max(len(rows), 1)
            r["jsonl"][p] = {"bytes": sib[p], "est_rows": int(sib[p] / bpr) if bpr else None,
                             "keys": sorted({k for x in rows if isinstance(x, dict) for k in x}),
                             "rows": [trunc(x) for x in rows[:3]],
                             "rows_full_for_tokens": [trunc(x, 20000) for x in rows[:5]]}
    r["file_list_sample"] = sorted(sib)[:40]
    return r


if __name__ == "__main__":
    repo = sys.argv[1]
    files = sys.argv[2:] or None
    res = recon(repo, files)
    (OUT / (repo.replace("/", "__") + ".json")).write_text(json.dumps(res, indent=1, default=str))
    print("ok", repo)
