"""brain serve — WS server + stdin REPL (each line = one final utterance).
brain eval-route — run the router over eval cases and write a JSON report.
brain trace-stats — p50/p95 latency report over runs/traces."""

import argparse
import asyncio
import json
import os
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


def route_catalog() -> Catalog:
    """Catalog the router/ARGS prompts are rendered over: MUSELET_ROUTE_CATALOG (it3: catalog v3), else skills/."""
    return Catalog.load(os.environ.get("MUSELET_ROUTE_CATALOG") or None)


async def _stdin_lines():
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            return
        line = line.rstrip("\n")
        if line:
            yield line


def planner_opts(args) -> dict:
    """Planner decoding/prompt knobs from `brain serve` flags."""
    fs = args.planner_fewshot
    opts = {"constrain": args.planner_constrain,
            "done_alone": args.planner_done_alone,
            "few_shot": None if fs is None or fs.lower() == "none" else fs,
            "history": args.planner_history}
    if args.planner_retrieval_k > 0:
        opts["retrieval_k"] = args.planner_retrieval_k
        opts["retrieval_bank"] = args.planner_retrieval_bank
    if args.planner_think > 0:
        opts["think_budget"] = args.planner_think
        opts["think_on"] = args.planner_think_on
        opts["think_sampler"] = args.planner_think_sampler
    opts["app_hints"] = args.planner_app_hints == "on"
    if opts["constrain"] is None:      # Planner's PLANNER_CONSTRAIN_DEFAULT
        del opts["constrain"]
    return opts


def make_planner(pmodel: str, engine=None, opts: dict | None = None,
                 tag: str = "planner", agentic_apps: bool = False,
                 mode: str = "dsl"):
    from .planner import Planner
    catalog = Catalog.load()
    planner_opts = dict(opts or {})
    if agentic_apps:
        planner_opts["hidden_skills"] = catalog.app_skills()
    if mode == "tools":       # native chat-template tool calling (experiment)
        from .native_planner import NativeToolPlanner
        planner = NativeToolPlanner(
            pmodel, catalog, engine=engine,
            app_hints=bool(planner_opts.get("app_hints")),
            hidden_skills=planner_opts.get("hidden_skills", ()))
    else:
        planner = Planner(pmodel, catalog, engine=engine, **planner_opts)
    if tag == "planner-aux":
        print(f"[{tag}] {pmodel} (separate)", flush=True)
    else:
        print(f"[{tag}] {pmodel} {planner.settings()}", flush=True)
    return planner


def grounder_cfg(args) -> dict:
    """`brain serve --grounder-*` -> Orchestrator.grounder_cfg ({} = disabled). Validates the adapter
    name without importing MLX."""
    spec = (args.grounder_model or "none").strip()
    if spec.lower() == "none":
        return {}
    from .grounder import get_adapter
    name, _, repo = spec.partition("=")
    get_adapter(name)
    return {"model": name, "repo": repo or None, "max_pixels": args.grounder_max_pixels,
            "zoom_frac": args.grounder_zoom_frac}


# escalation planner: few-shot on, unconstrained, dsl history
ESCALATE_OPTS = {"constrain": False, "few_shot": "prompts/planner_fewshot.md",
                 "history": "dsl"}


def _mode_kw(mode: str | None) -> dict:
    return {"mode": mode} if mode and mode != "dsl" else {}


async def serve(port: int = 8765, model: str | None = None,
                planner_model: str | None = None,
                planner_kw: dict | None = None,
                args_model: str | None = None,
                escalate_model: str | None = None,
                grounder: dict | None = None,
                memory_enabled: bool = True,
                memory_llm: bool = True,
                longterm_enabled: bool = True,
                verify_done: bool = True,
                planner_aux_model: str | None = "planner",
                fallback_planner: bool = False,
                planner_context: bool = False,
                open_ended_route: bool = False,
                planner_blind: str = "base",
                agentic_apps: bool = True,
                planner_mode: str = "dsl",
                planner_blind_mode: str | None = None):
    server = BrainServer(port=port)
    await server.start()
    engine = None
    if model:
        from .decision import DecisionEngine
        engine = DecisionEngine(model, route_catalog(), args_model_path=args_model)
        print(f"[engine] {model}", flush=True)
        print(f"[args] {engine.args_model_path}", flush=True)
    planner = None
    pmodel = _resolve_model(planner_model)
    if pmodel:
        planner = make_planner(pmodel, engine, planner_kw,
                               agentic_apps=agentic_apps, **_mode_kw(planner_mode))
    blind_mode = _mode_kw(planner_blind_mode or planner_mode)
    orch = Orchestrator(server, Catalog.load(), Tracer(), engine=engine,
                        open_ended_route=open_ended_route)
    orch.agentic_apps = agentic_apps
    orch.planner = planner
    if planner is None:
        orch.planner_aux = None
        print("[planner-aux] none", flush=True)
    elif planner_aux_model is None or planner_aux_model == "planner":
        orch.planner_aux = planner
        print(f"[planner-aux] {pmodel} (shared)", flush=True)
    else:
        aux_path = _resolve_model(planner_aux_model)
        if aux_path == pmodel:
            orch.planner_aux = planner
            print(f"[planner-aux] {aux_path} (shared)", flush=True)
        elif aux_path is None:
            orch.planner_aux = None
            print("[planner-aux] none", flush=True)
        else:
            orch.planner_aux = make_planner(
                aux_path, engine,
                {"few_shot": None, "constrain": False},
                tag="planner-aux", agentic_apps=agentic_apps)
    # blind/open-ended tasks plan with the base model (few-shot + think),
    # reusing the aux weights so no extra load when aux == base.
    orch.planner_blind = None
    if planner is not None and planner_blind == "escalate":
        orch.planner_blind = make_planner(
            escalate_model or "mlx-community/Qwen3.6-35B-A3B-4bit", engine,
            {**ESCALATE_OPTS, "retrieval_k": 1, "retrieval_bank": "v2-tune",
             "app_hints": bool((planner_kw or {}).get("app_hints")),
             "think_budget": 512, "think_on": "all", "think_sampler": "qwen"},
            tag="planner-blind", agentic_apps=agentic_apps, **blind_mode)
        orch._schedule_warm_planner(orch.planner_blind, "planner-blind")
        print(f"[planner-blind] {orch.planner_blind.model_path} "
              f"(escalate)", flush=True)
    elif planner is not None and planner_blind == "base":
        aux_model = orch.planner_aux
        blind_path = _resolve_model(
            planner_aux_model if isinstance(planner_aux_model, str)
            and planner_aux_model not in (None, "planner") else None)
        blind_path = blind_path or getattr(aux_model, "model_path", None) \
            or _resolve_model(None)
        if blind_path:
            orch.planner_blind = make_planner(
                blind_path, engine,
                {"few_shot": "prompts/planner_fewshot.md", "retrieval_k": 1,
                 "retrieval_bank": "v2-tune", "think_budget": 512,
                 "think_on": "all", "think_sampler": "qwen"},
                tag="planner-blind", agentic_apps=agentic_apps, **blind_mode)
            print(f"[planner-blind] {blind_path} (base-config, "
                  f"shared weights)", flush=True)
    orch.memory_enabled = memory_enabled
    orch.memory_llm = memory_llm
    orch.longterm_enabled = bool(longterm_enabled and memory_enabled)
    orch.verify_done = verify_done
    orch.fallback_planner = fallback_planner
    orch.planner_context = planner_context
    print(f"[planner] verify_done={'on' if verify_done else 'off'} "
          f"fallback={'on' if fallback_planner else 'off'} "
          f"context={'on' if planner_context else 'off'} "
          f"agentic_apps={'on' if agentic_apps else 'off'}",
          flush=True)
    esc = {**ESCALATE_OPTS, **{k: v for k, v in (planner_kw or {}).items()
                               if k.startswith("think_")}}
    orch.escalate_opts = esc
    orch._schedule_warm_planner(planner)
    orch.escalate_model = escalate_model or \
        "mlx-community/Qwen3.6-35B-A3B-4bit"
    if grounder is not None:
        orch.grounder_cfg = grounder or None      # {} = disabled
    if orch.grounder_cfg:                         # weights prewarm off-thread; see _schedule_warm_grounder
        print(f"[grounder] {orch.grounder_cfg['model']} max_pixels={orch.grounder_cfg['max_pixels']} "
              f"zoom_frac={orch.grounder_cfg['zoom_frac']} (lazy)", flush=True)
        orch._schedule_warm_grounder()

    async def on_hello(screens):
        orch.screens = screens

    server.on_hello = on_hello
    if planner and escalate_model:    # loaded now, kept resident
        orch.planner_escalate = make_planner(
            escalate_model, engine, esc, tag="planner-escalate",
            agentic_apps=agentic_apps)
        orch._schedule_warm_planner(
            orch.planner_escalate, "planner-escalate")

    async def on_utt(text: str, final: bool, ctx: dict | None = None):
        print(f"[utterance] {text} ctx={ctx}", flush=True)
        await orch.handle_utterance(text, ctx)

    server.on_utterance = on_utt
    async def on_config(msg):
        result = {}
        if "escalate_planner" in msg:
            # MUSELET_NO_ESCALATE=1: the app's 35B-fallback toggle is ignored
            # (single-model experiments)
            want = bool(msg.get("escalate_planner")) and \
                os.environ.get("MUSELET_NO_ESCALATE") != "1"
            result.update(await orch.set_escalation(want))
        if "memory" in msg:
            orch.memory_enabled = bool(msg["memory"])
            orch.longterm_enabled = bool(
                msg["memory"] and longterm_enabled)
            result["memory"] = orch.longterm_enabled
            result.setdefault("loaded", True)
        return result

    async def on_memory(msg):
        return orch.memory_request(msg)

    server.on_config = on_config
    server.on_memory = on_memory
    server.on_partial = lambda t, c=None: orch._speculative_route(t, c)
    server.on_confirm_interrupt = getattr(orch, "confirm_interrupt", None)
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


def eval_route(model: str, cases_path: str, out_dir: str = "runs/evals",
               tau: float = 0.55, args_model: str | None = None):
    import subprocess

    from .decision import DecisionEngine
    try:
        cases_sha = subprocess.run(
            ["git", "hash-object", cases_path],
            capture_output=True, text=True).stdout.strip()
    except Exception:
        cases_sha = ""
    cases = [json.loads(l) for l in Path(cases_path).read_text().splitlines()
             if l.strip()]
    engine = DecisionEngine(_resolve_model(model), route_catalog(),
                            args_model_path=_resolve_model(args_model)
                            if args_model else None)
    print(f"[args] {engine.args_model_path}", flush=True)
    from .orchestrator import Orchestrator
    dummy_orch = Orchestrator.__new__(Orchestrator)
    dummy_orch.catalog = Catalog.load()
    pairs: list[tuple[str, str]] = []   # (true, predicted)
    route_ms, args_ms, probs_ece = [], [], []
    correct = n_args_scored = e2e_n = raw_correct = 0
    args_hits = e2e_hits = 0
    confusions: dict = {}

    def args_match(got: dict, gold: dict) -> bool:
        if set(got) != set(gold):
            return False
        for k, gv in gold.items():
            v = got[k]
            if isinstance(gv, (int, float)) and isinstance(v, (int, float)):
                if v != gv:
                    return False
            elif str(v).strip().lower() != str(gv).strip().lower():
                return False
        return True

    for c in cases:
        r = engine.route(c["utterance"], c.get("ctx", {}))
        route_ms.append(r.ms["route_ms"])
        lab, lbl = r.top, c["label"]
        raw_correct += lab == lbl
        if r.p_top < tau:
            lab = "MULTI_STEP"     # serve sends unsure routes to the planner
        pairs.append((lbl, lab))
        if lab == lbl:
            correct += 1
        else:
            confusions[(lbl, lab)] = confusions.get((lbl, lab), 0) + 1
        probs_ece.append((r.p_top, lab == lbl))
        if c.get("args"):
            e2e_n += 1
            if lab == lbl:
                ext = engine.args(lab, c["utterance"], c.get("ctx", {}))
                args_ms.append(ext["ms"]["args_ms"])
                got = {k: v for k, v in ext.items()
                       if k not in ("ms", "_raw", "missing")}
                got = Orchestrator._coerce_args(dummy_orch, lab, got,
                                                utterance=c["utterance"])
                got = {k: got[k] for k in c["args"] if k in got}
                n_args_scored += 1
                if args_match(got, c["args"]):
                    args_hits += 1
                    e2e_hits += 1

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

    labels = sorted({t for t, _ in pairs})   # gold labels only
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
        "model": model, "n": len(cases), "cases_sha": cases_sha,
        "accuracy": correct / len(cases) if cases else 0,
        "accuracy_top1_ungated": raw_correct / len(cases) if cases else 0,
        "tau": tau,
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0,
        "per_label": per_label,
        "top_confusions": [
            {"gold": g, "pred": p, "n": n}
            for (g, p), n in sorted(confusions.items(), key=lambda kv: -kv[1])[:10]],
        "args_exact": args_hits / n_args_scored if n_args_scored else None,
        "n_args_scored": n_args_scored,
        "e2e_exact": e2e_hits / e2e_n if e2e_n else None,
        "ece_15": round(ece, 4),
        "route_ms": {"p50": pct(route_ms, .5), "p95": pct(route_ms, .95)},
        "args_ms": {"p50": pct(args_ms, .5), "p95": pct(args_ms, .95)},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = Path(out_dir) / f"route_{int(time.time())}.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def main():
    args, ap = build_parser()
    run_cmd(args, ap)


def build_parser(argv=None):
    ap = argparse.ArgumentParser(prog="brain")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="run the WS server + stdin REPL")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--memory", action=argparse.BooleanOptionalAction,
                   default=True, help="enable short-term working memory")
    s.add_argument("--memory-llm", action=argparse.BooleanOptionalAction,
                   default=True, help="allow guarded LLM follow-up rewrites")
    s.add_argument("--longterm", action=argparse.BooleanOptionalAction,
                   default=True, help="enable on-device long-term memory")
    s.add_argument("--model", default=None,
                   help="model path/repo; 'none' = regex fallback; "
                        "default: 4B-4bit if cached else 0.8B-4bit")
    s.add_argument("--tau", type=float, default=0.55)
    s.add_argument("--args-model", default=None,
                   help="model for ARGS; default: same as --model")
    s.add_argument("--planner-model", default=None,
                   help="planner model; default: cached Qwen3.5-4B-4bit")
    s.add_argument("--planner-aux-model",
                   default="mlx-community/Qwen3.5-4B-4bit",
                   metavar="PATH|planner",
                   help=("model for non-planning text/decide calls (memory "
                         "rewrite, verify-done, web answers, compose_text, "
                         "email bodies, fallback answers); `planner` = reuse "
                         "the planner model"))
    s.add_argument("--verify-done", choices=("on", "off"), default="on",
                   help="verify planner done (expect or model check) + bounded recovery; off = old behaviour")
    s.add_argument("--fallback-planner", choices=("on", "off"), default="off",
                   help="hand recoverable safe skill/tool failures to the planner once")
    s.add_argument("--planner-context", choices=("on", "off"), default="off",
                   help="include request ctx and a compact screen summary on the planner's first turn")
    s.add_argument("--open-ended-route", choices=("on", "off"), default="off")
    s.add_argument("--agentic-apps", choices=("on", "off"), default="on",
                   help="operate app skills through the planner")
    s.add_argument("--planner-blind", choices=("base", "planner", "escalate"),
                   default="base",
                   help="planner for blind/open-ended tasks: base = aux model "
                        "with few-shot + think 512; planner = shipped planner")
    s.add_argument("--planner-mode", choices=("dsl", "tools"), default="dsl",
                   help="main planner output: dsl = constrained DSL batches; tools = native "
                        "chat-template tool calls, one per turn (experiment)")
    s.add_argument("--planner-blind-mode", choices=("dsl", "tools"), default=None,
                   help="blind/open-ended planner output (default: --planner-mode)")
    s.add_argument("--planner-constrain", action=argparse.BooleanOptionalAction,
                   default=None, help="line-start DSL op constraint "
                   "(default: planner.PLANNER_CONSTRAIN_DEFAULT)")
    s.add_argument("--planner-done-alone", action=argparse.BooleanOptionalAction,
                   default=True, help="block `done` after an action line")
    s.add_argument("--planner-fewshot", default="prompts/planner_fewshot.md",
                   metavar="PATH|none", help="few-shot examples in the cached prefix")
    s.add_argument("--planner-escalate-model", default=None, metavar="PATH",
                   help="opt-in planner that takes over when the loop guard trips")
    s.add_argument("--planner-history", default="dsl",
                   choices=["marked", "dsl", "repr"], help="Last batch line format")
    s.add_argument("--planner-retrieval-k", type=int, choices=(0, 1, 2), default=0)
    s.add_argument("--planner-retrieval-bank", default="v2-tune",
                   metavar="v2-tune|hf[:REPO[:FILE]][@REV]|PATH",
                   help="HF bank defaults to bank.jsonl.gz; append @REV to pin a dataset revision")
    s.add_argument("--planner-think", type=int, default=0,
                   help="think-token budget before the action batch; 0 = off")
    s.add_argument("--planner-think-on", choices=("all", "retry"), default="all")
    s.add_argument("--planner-think-sampler", choices=("greedy", "qwen"), default="greedy")
    s.add_argument("--planner-app-hints", choices=("on", "off"), default="off")
    s.add_argument("--grounder-model", default="eyes-4b", metavar="NAME[=PATH]|none",
                   help="grounder adapter for `click \"<target>\"` (brain.grounder.ADAPTERS, e.g. "
                        "eyes-4b, ui-venus-1.5-8b; name=path for local weights); loaded on first use")
    s.add_argument("--grounder-max-pixels", type=int, default=1_000_000,
                   help="pixel cap per grounder screenshot/model call (2000000 = slower, more accurate)")
    s.add_argument("--grounder-zoom-frac", type=float, default=0.4,
                   help="stage-2 zoom region as a fraction of the window side")
    e = sub.add_parser("eval-route", help="eval the router on a JSONL cases file")
    e.add_argument("--model", default=None)
    e.add_argument("--args-model", default=None,
                   help="model for ARGS; default: same as --model")
    e.add_argument("--cases", required=True)
    e.add_argument("--out", default="runs/evals")
    e.add_argument("--tau", type=float, default=0.55,
                   help="below this p_top a case counts as MULTI_STEP (planner)")
    t = sub.add_parser("trace-stats", help="p50/p95 latency report over traces")
    t.add_argument("--since", default=None, help="ISO date/time lower bound")
    t.add_argument("--path", default="runs/traces",
                   help="trace dir or .jsonl file")
    t.add_argument("--json", action="store_true", help="print JSON")
    return ap.parse_args(argv), ap


def run_cmd(args, ap):
    if args.cmd == "trace-stats":
        from . import tracestats
        rep = tracestats.stats(tracestats.load(args.path, args.since))
        print(json.dumps(rep, indent=2) if args.json
              else tracestats.format_report(rep))
    elif args.cmd == "serve":
        m = _resolve_model(args.model)
        am = _resolve_model(args.args_model) if args.args_model else None
        em = args.planner_escalate_model
        em = _resolve_model(em) if em and em.lower() != "none" else None
        memory_kw = {}
        if not args.memory:
            memory_kw["memory_enabled"] = False
        if not args.memory_llm:
            memory_kw["memory_llm"] = False
        if not args.longterm or not args.memory:
            memory_kw["longterm_enabled"] = False
        asyncio.run(serve(
            args.port, m, args.planner_model, planner_opts(args),
            args_model=am, escalate_model=em, grounder=grounder_cfg(args),
            verify_done=args.verify_done == "on",
            planner_aux_model=args.planner_aux_model,
            fallback_planner=args.fallback_planner == "on",
            planner_context=args.planner_context == "on",
            open_ended_route=args.open_ended_route == "on",
            planner_blind=args.planner_blind,
            agentic_apps=args.agentic_apps == "on",
            planner_mode=args.planner_mode,
            planner_blind_mode=args.planner_blind_mode, **memory_kw))
    elif args.cmd == "eval-route":
        eval_route(args.model, args.cases, args.out,
                   tau=getattr(args, "tau", 0.55), args_model=args.args_model)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
