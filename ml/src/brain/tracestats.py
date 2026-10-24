"""brain trace-stats — p50/p95 latency report over runs/traces/*.jsonl."""

import json
from datetime import datetime
from pathlib import Path

METRICS = ("release_to_first_action_ms", "route_ms", "args_ms",
           "planner_ttft_ms", "decode_tok_s", "total_ms")


def pct(xs: list[float], p: float) -> float | None:
    """nearest-rank percentile (p in 0..100)."""
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, -(-len(xs) * p // 100) - 1))
    return round(xs[int(k)], 1)


def load(path: str | Path, since: str | None = None) -> list[dict]:
    p = Path(path)
    files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
    t0 = datetime.fromisoformat(since) if since else None
    out = []
    for f in files:
        for ln in f.read_text().splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if t0 and r.get("ts"):
                ts = datetime.fromisoformat(r["ts"])
                if (ts.tzinfo is None) != (t0.tzinfo is None):
                    ts, cmp = ts.replace(tzinfo=None), t0.replace(tzinfo=None)
                else:
                    cmp = t0
                if ts < cmp:
                    continue
            out.append(r)
    return out


def metrics(r: dict) -> dict:
    """one trace -> {metric: value} plus label / spec_hit / slot_fill."""
    m: dict = {"label": None, "spec_hit": None,
               "slot_fill": bool(r.get("slot_fill"))}
    if r.get("release_to_first_action_ms") is not None:
        m["release_to_first_action_ms"] = r["release_to_first_action_ms"]
    total = r.get("total_ms", (r.get("stages") or {}).get("total"))
    if total is not None:
        m["total_ms"] = total
    ttft, tps = [], []
    for d in r.get("decisions") or []:
        if not isinstance(d, dict):
            continue
        if d.get("route_ms") is not None:
            m["route_ms"] = d["route_ms"]
        if "route_probs" in d and m["label"] is None and d["route_probs"]:
            m["label"] = d["route_probs"][0][0]
        if "spec_hit" in d:
            m["spec_hit"] = bool(d["spec_hit"])
        if d.get("args_ms") is not None:
            m["args_ms"] = d["args_ms"]
        if "planner_turn" in d:
            if d.get("ttft_ms") is not None:
                ttft.append(d["ttft_ms"])
            if d.get("decode_tok_s"):
                tps.append(d["decode_tok_s"])
        if isinstance(d.get("router"), dict) and m["label"] is None:
            rt = d["router"]
            m["label"] = rt.get("name") or rt.get("kind")
        if d.get("slot_fill") is not None:
            m["slot_fill"] = True
    if ttft:
        m["planner_ttft_ms"] = ttft[0]       # first turn = user-felt TTFT
    if tps:
        m["decode_tok_s"] = sum(tps) / len(tps)
    m["label"] = m["label"] or "none"
    return m


def _block(rows: list[dict]) -> dict:
    out = {"n": len(rows)}
    for k in METRICS:
        xs = [r[k] for r in rows if r.get(k) is not None]
        if xs:
            out[k] = {"p50": pct(xs, 50), "p95": pct(xs, 95), "n": len(xs)}
    return out


def stats(traces: list[dict]) -> dict:
    rows = [dict(metrics(r), outcome=r.get("outcome") or "none")
            for r in traces]
    spec = [r["spec_hit"] for r in rows if r["spec_hit"] is not None]
    rep = {"n": len(rows), "all": _block(rows),
           "spec_hit_rate": round(sum(spec) / len(spec), 3) if spec else None,
           "spec_n": len(spec),
           "slot_fill": sum(r["slot_fill"] for r in rows),
           "by_outcome": {}, "by_label": {}}
    for key, grp in (("outcome", "by_outcome"), ("label", "by_label")):
        for v in sorted({r[key] for r in rows}):
            rep[grp][v] = _block([r for r in rows if r[key] == v])
    return rep


def format_report(rep: dict) -> str:
    cols = ["n"] + [m.replace("_ms", "").replace("release_to_first_action",
                                                 "first_act") for m in METRICS]
    lines = [f"traces: {rep['n']}  spec_hit: "
             f"{rep['spec_hit_rate'] if rep['spec_hit_rate'] is not None else '-'}"
             f" (of {rep['spec_n']})  slot_fill: {rep['slot_fill']}",
             "p50/p95 " + " ".join(f"{c:>15}" for c in cols)]

    def row(name, b):
        cells = [f"{b['n']:>15}"]
        for m in METRICS:
            v = b.get(m)
            cells.append(f"{(str(v['p50']) + '/' + str(v['p95'])) if v else '-':>15}")
        return f"{name[:22]:<22}" + " ".join(cells)
    lines.append(row("all", rep["all"]))
    for grp in ("by_outcome", "by_label"):
        lines.append(f"-- {grp.replace('_', ' ')}")
        for k, b in rep[grp].items():
            lines.append(row(f"  {k}", b))
    return "\n".join(lines)
