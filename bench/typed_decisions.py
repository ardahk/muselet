"""Run the pinned Typed Decisions test split against a System One endpoint."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REVISION = "80cb93ae477fdfc91e3b6114f7a281c444dda843"
HF_REPO = "LocalLLaMA/typed-decisions"
# score_one and the ten-bin ECE below are copied verbatim from
# LocalLLaMA/typed-decisions:bench/score_with_jobs.py at REVISION.


def score_one(pred, gold):
    """Verbatim from bench/score_with_jobs.py at the pinned HF revision."""
    opts = list(gold["probabilities"].keys())
    g = [float(gold["probabilities"][o]) for o in opts]
    if gold["type"] == "noul":  # engines report yes/no; gold uses true/false
        pred = dict(pred)
        pred["probabilities"] = {
            {"yes": "true", "no": "false"}.get(k, k): v for k, v in pred["probabilities"].items()
        }
    p = [float(pred["probabilities"].get(o, 0.0)) for o in opts]
    s = sum(p)
    p = [v / s for v in p] if s > 0 else [1.0 / len(opts)] * len(opts)
    am_p = p.index(max(p))
    am_g = g.index(max(g))
    kl = sum(gi * math.log(gi / max(pi, 1e-9)) for gi, pi in zip(g, p) if gi > 0)
    brier = sum((pi - gi) ** 2 for pi, gi in zip(p, g))
    return am_p == am_g, kl, brier, max(p)


def ece(confidences, n_bins=10):
    """Verbatim bin accumulation from bench/score_with_jobs.py."""
    n = len(confidences)
    bin_hits = [0] * n_bins
    bin_total = [0] * n_bins
    bin_conf = [0.0] * n_bins
    for ok, conf in confidences:
        b = min(int(conf * n_bins), n_bins - 1)
        bin_total[b] += 1
        bin_hits[b] += int(ok)
        bin_conf[b] += conf
    error = 0.0
    for b in range(n_bins):
        if bin_total[b]:
            error += bin_total[b] / n * abs(bin_hits[b] / bin_total[b] - bin_conf[b] / bin_total[b])
    return error


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lower, upper = math.floor(k), math.ceil(k)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - k) + ordered[upper] * (k - lower)


def _fetch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://huggingface.co/datasets/{HF_REPO}/resolve/{REVISION}/"
        "all/test-00000-of-00001.parquet?download=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "MuseletBench/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    return path


def _post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/systemone",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read())


def _metric(rows):
    n = len(rows)
    return {
        "n": n,
        "accuracy": sum(row["correct"] for row in rows) / n if n else None,
        "kl_from_gold": sum(row["kl"] for row in rows) / n if n else None,
        "brier": sum(row["brier"] for row in rows) / n if n else None,
        "ece": ece([(row["correct"], row["confidence"]) for row in rows]) if rows else None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8793")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default="muselet")
    parser.add_argument("--parquet", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/bench/typed_decisions"))
    parser.add_argument("--out-root", type=Path, default=Path("runs/bench/typed_decisions"))
    args = parser.parse_args(argv)

    import pyarrow.parquet as parquet

    parquet_path = args.parquet or args.data_dir / "test-00000-of-00001.parquet"
    if not parquet_path.is_file():
        _fetch(parquet_path)
    table = parquet.read_table(parquet_path)
    source_rows = table.to_pylist()
    if args.limit is not None:
        source_rows = source_rows[:args.limit]

    run_dir = args.out_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    (run_dir / "command.txt").write_text(
        f"python3 -m bench.typed_decisions --url {args.url} --model {args.model}"
        + (f" --limit {args.limit}" if args.limit is not None else "")
        + f"\nHF repository: {HF_REPO}\nHF revision: {REVISION}\n",
        encoding="utf-8",
    )
    per_kind = defaultdict(list)
    latencies = []
    predictions = []
    for raw in source_rows:
        payload = {
            "model": args.model,
            "state": json.loads(raw["state"]),
            "questions": json.loads(raw["questions"]),
        }
        started = time.perf_counter()
        answer = _post(args.url, payload)
        latency = time.perf_counter() - started
        latencies.append(latency)
        gold = json.loads(raw["gold"])
        row_record = {"id": raw["id"], "latency_s": latency, "answers": answer.get("answers", {})}
        for qid, target in gold.items():
            predicted = answer["answers"].get(qid, {"probabilities": {}})
            result = score_one(predicted, target)
            kind = json.loads(raw["questions"])[qid]["type"]
            metric_row = {
                "correct": result[0], "kl": result[1], "brier": result[2], "confidence": result[3],
            }
            per_kind[kind].append(metric_row)
            row_record.setdefault("scores", {})[qid] = {"type": kind, **metric_row}
        predictions.append(row_record)
    (run_dir / "predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
    )
    all_rows = [row for values in per_kind.values() for row in values]
    summary = {
        "model": args.model,
        "dataset": HF_REPO,
        "revision": REVISION,
        "n_cases": len(source_rows),
        "n_decisions": len(all_rows),
        "overall": _metric(all_rows),
        "by_question_type": {kind: _metric(rows) for kind, rows in sorted(per_kind.items())},
        "request_latency_s": {
            "n": len(latencies), "p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
