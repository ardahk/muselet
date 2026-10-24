"""brain serve — WS server + stdin REPL (each line = one final utterance).
brain eval-route — run the router over eval cases and write a JSON report."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from .catalog import Catalog
from .orchestrator import Orchestrator
from .server import BrainServer
from .traces import Tracer


def _resolve_model(arg: str) -> str | None:
    """'none' -> None. Otherwise a local HF snapshot path (downloaded models)."""
    if arg is None:
        candidates = ["mlx-community/Qwen3.5-4B-4bit",
                      "mlx-community/Qwen3.5-0.8B-4bit"]
    elif arg in ("none", "None", ""):
        return None
    else:
        candidates = [arg]
    from huggingface_hub import snapshot_download
    for repo in candidates:
        if Path(repo).exists():
            return repo
        try:
            return snapshot_download(repo, local_files_only=True)
        except Exception:
            continue
    return arg if candidates == [arg] else None


async def _stdin_lines():
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            return
        line = line.rstrip("\n")
        if line:
            yield line


async def serve(port: int = 8765, model: str | None = None):
    server = BrainServer(port=port)
    await server.start()
    engine = None
    if model:
        from .decision import DecisionEngine
        engine = DecisionEngine(model, Catalog.load())
        print(f"[engine] {model}", flush=True)
    orch = Orchestrator(server, Catalog.load(), Tracer(), engine=engine)

    async def on_utt(text: str, final: bool):
        print(f"[utterance] {text}", flush=True)
        await orch.handle_utterance(text)

    server.on_utterance = on_utt
    print(f"brain listening on ws://127.0.0.1:{server.port}", flush=True)
    print("type an utterance + enter (headless mode)", flush=True)

    try:
        async for line in _stdin_lines():
            print(f"[stdin] {line}", flush=True)
            try:
                await orch.handle_utterance(line)
            except Exception as e:  # keep the REPL alive
                print(f"[error] {e!r}", flush=True)
        # stdin closed (e.g. daemon mode): keep serving WS clients
        print("[stdin closed] serving WS only", flush=True)
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.close()


def eval_route(model: str, cases_path: str, out_dir: str = "runs/evals"):
    from .decision import DecisionEngine
    cases = [json.loads(l) for l in Path(cases_path).read_text().splitlines()
             if l.strip()]
    engine = DecisionEngine(_resolve_model(model), Catalog.load())
    pairs: list[tuple[str, str]] = []   # (true, predicted)
    route_ms, args_ms, probs_ece = [], [], []
    correct = exact_args = n_args = 0
    for c in cases:
        r = engine.route(c["utterance"], c.get("ctx", {}))
        route_ms.append(r.ms["route_ms"])
        lab, lbl = r.top, c["label"]
        pairs.append((lbl, lab))
        if lab == lbl:
            correct += 1
        probs_ece.append((r.p_top, lab == lbl))
        if c.get("args") and lab not in ("MULTI_STEP", "ASK", "REFUSE", "ANSWER"):
            ext = engine.args(lab, c["utterance"], c.get("ctx", {}))
            args_ms.append(ext["ms"]["args_ms"])
            n_args += 1
            got = {k: v for k, v in ext.items() if k not in ("ms", "_raw")}
            if got == c["args"]:
                exact_args += 1

    def pct(ts, p):
        ts = sorted(ts)
        return ts[min(len(ts) - 1, int(len(ts) * p))] if ts else 0

    # ECE, 15 bins
    ece = 0.0
    for b in range(15):
        lo, hi = b / 15, (b + 1) / 15
        bin_items = [x for x in probs_ece if lo <= x[0] < hi or (b == 14 and x[0] == 1)]
        if bin_items:
            acc = sum(x[1] for x in bin_items) / len(bin_items)
            conf = sum(x[0] for x in bin_items) / len(bin_items)
            ece += len(bin_items) / len(probs_ece) * abs(acc - conf)

    labels = sorted({t for t, _ in pairs} | {p for _, p in pairs})
    per_label: dict = {}
    f1s = []
    for l in labels:
        tp = sum(1 for t, p in pairs if t == l and p == l)
        fp = sum(1 for t, p in pairs if t != l and p == l)
        fn = sum(1 for t, p in pairs if t == l and p != l)
        support = tp + fn
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        f1s.append(f1)
        per_label[l] = {"acc": rec, "n": support, "f1": f1}
    report = {
        "model": model, "n": len(cases),
        "accuracy": correct / len(cases) if cases else 0,
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0,
        "per_label": per_label,
        "ece_15": round(ece, 4),
        "route_ms": {"p50": pct(route_ms, .5), "p95": pct(route_ms, .95)},
        "args_ms": {"p50": pct(args_ms, .5), "p95": pct(args_ms, .95)},
        "args_exact": exact_args / n_args if n_args else None,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = Path(out_dir) / f"route_{int(time.time())}.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="brain")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="run the WS server + stdin REPL")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--model", default=None,
                   help="model path/repo; 'none' = regex fallback; "
                        "default: 4B-4bit if cached else 0.8B-4bit")
    s.add_argument("--tau", type=float, default=0.55)
    e = sub.add_parser("eval-route", help="eval the router on a JSONL cases file")
    e.add_argument("--model", default=None)
    e.add_argument("--cases", required=True)
    e.add_argument("--out", default="runs/evals")
    args = ap.parse_args()
    if args.cmd == "serve":
        m = _resolve_model(args.model)
        asyncio.run(serve(args.port, m))
    elif args.cmd == "eval-route":
        eval_route(args.model, args.cases, args.out)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
