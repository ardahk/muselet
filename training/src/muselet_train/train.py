"""Phase 1 training on Tinker (SPEC 1.6): Qwen3.5-4B LoRA, soft route targets + ARGS SFT.

A pre-flight cost estimate runs before the training client is created; the run aborts above --max-usd.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import random
import time
from pathlib import Path

import tinker

from muselet_train import datums as D
from muselet_train.catalog import option_names, skill_by_name
from muselet_train.evalcheck import check_rows
from muselet_train.route_render import (
    STUDENT_MODEL, RouteContext, args_messages, args_runtime_prompt, base_renderer, render_route)
from muselet_train.teacher import chunked_decision

PRICE_TRAIN, PRICE_PREFILL = 0.73, 0.33  # Qwen3.5-4B, SPEC prices per 1M tokens
OUT = Path("/data/train")
REPORTS = Path(__file__).resolve().parents[2] / "reports"


def route_metrics(rows: list[tuple[str, dict[str, float]]]) -> dict:
    names = option_names()
    n = len(rows)
    correct, brier, bins = 0, 0.0, [[0, 0.0, 0.0] for _ in range(15)]
    tp, fp, fn, per = collections.Counter(), collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for label, p in rows:
        top = max(p, key=p.get)
        ok = top == label
        correct += ok
        per[label].append(ok)
        tp[label] += ok
        if not ok:
            fp[top] += 1
            fn[label] += 1
        brier += sum((p.get(k, 0.0) - (k == label)) ** 2 for k in names)
        b = bins[min(int(p[top] * 15), 14)]
        b[0] += 1
        b[1] += p[top]
        b[2] += ok
    f1 = [2 * tp[k] / (2 * tp[k] + fp[k] + fn[k]) for k in per if 2 * tp[k] + fp[k] + fn[k]]
    return {"n": n, "top1": correct / n, "macro_f1": sum(f1) / len(f1),
            "ece": sum(abs(c - s) for m, s, c in bins if m) / n, "brier": brier / n,
            "per_label": {k: sum(v) / len(v) for k, v in sorted(per.items())},
            "per_label_n": {k: len(v) for k, v in sorted(per.items())}}


def _text(msg) -> str:
    c = msg["content"]
    return c if isinstance(c, str) else "".join(x.get("text", "") for x in c if x.get("type") == "text")


async def evaluate(client, val_route: list[D.RouteItem], val_args: list[dict], model: str, conc: int = 32) -> dict:
    sem = asyncio.Semaphore(conc)
    rend = base_renderer(model)
    im_end = rend.tokenizer.convert_tokens_to_ids("<|im_end|>")

    async def one_route(it):
        async with sem:
            return it.label, await chunked_decision(client, render_route(RouteContext(**it.context), it.utterance, model))

    async def one_args(r):
        msgs = args_messages(skill_by_name(r["skill"]), RouteContext(**r["context"]), r["utterance"])
        async with sem:
            res = await client.sample_async(
                prompt=rend.build_generation_prompt(msgs), num_samples=1,
                sampling_params=tinker.SamplingParams(max_tokens=64, temperature=0.0, stop=rend.get_stop_sequences()))
        got = _text(rend.parse_response(res.sequences[0].tokens)[0]).strip()
        prompt = args_runtime_prompt(rend, skill_by_name(r["skill"]), RouteContext(**r["context"]), r["utterance"])
        async with sem:
            rt = await client.sample_async(
                prompt=tinker.ModelInput.from_ints(prompt), num_samples=1,
                sampling_params=tinker.SamplingParams(max_tokens=24, temperature=0.0, stop=[im_end]))
        out = []
        for t in rt.sequences[0].tokens:  # DecisionEngine.args: greedy, stop at <|im_end|> or a newline token
            if t == im_end or "\n" in rend.tokenizer.decode([t]):
                break
            out.append(t)
        got_rt = rend.tokenizer.decode(out).strip()
        want = " ".join(r["target"].split())
        return " ".join(got.split()) == want, " ".join(got_rt.split()) == want, got_rt == "" and want != ""

    routes = await asyncio.gather(*(one_route(it) for it in val_route))
    em = await asyncio.gather(*(one_args(r) for r in val_args))
    n = max(len(em), 1)
    return {**route_metrics(routes), "args_em": sum(e[0] for e in em) / n, "args_em_runtime": sum(e[1] for e in em) / n,
            "args_empty_runtime": sum(e[2] for e in em) / n, "args_n": len(em)}


def write_report(name: str, cfg: dict, history: list[dict], ckpts: list[dict], final: dict | None = None,
                 data: dict | None = None) -> Path:
    last = history[-1] if history else {}
    lines = [f"# Phase 1 run `{name}`", "", "```json", json.dumps(cfg, indent=1), "```", "",
             "| step | train loss | val top1 | macro-F1 | ECE | Brier | ARGS EM | ARGS EM runtime | ARGS empty runtime (non-empty target) |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {h['step']} | {h.get('train_loss', float('nan')):.4f} | {h['top1']:.3f} | {h['macro_f1']:.3f} | "
              f"{h['ece']:.3f} | {h['brier']:.3f} | {h['args_em']:.3f} | {h.get('args_em_runtime', float('nan')):.3f} | "
              f"{h.get('args_empty_runtime', float('nan')):.3f} |" for h in history if "top1" in h]
    if final:
        lines += ["", f"Final eval on the full val split ({final['n']} route, {final['args_n']} ARGS): top1 "
                  f"{final['top1']:.3f}, macro-F1 {final['macro_f1']:.3f}, ECE {final['ece']:.3f}, "
                  f"Brier {final['brier']:.3f}, ARGS EM {final['args_em']:.3f}, ARGS EM with the runtime rendering "
                  f"(gate) {final.get('args_em_runtime', float('nan')):.3f}, "
                  f"empty on non-empty targets {final.get('args_empty_runtime', float('nan')):.3f}"]
    src = final or last
    if src.get("per_label"):
        n = src.get("per_label_n", {})
        lines += ["", f"Per-label val accuracy ({'full val split' if final else 'last eval'}; n = val items):", "",
                  "| label | acc | n |", "|---|---|---|"]
        lines += [f"| {k} | {v:.3f} | {n.get(k, '')} |" for k, v in src["per_label"].items()]
    if data:
        lines += ["", "Data:", "", "```json", json.dumps(data, indent=1), "```"]
    lines += ["", "Checkpoints:", ""] + [f"- step {c['step']}: `{c['path']}`" for c in ckpts]
    p = REPORTS / f"phase1_{name}.md"
    p.write_text("\n".join(lines) + "\n")
    return p


async def main_async(a) -> None:
    stats, dropped = {}, set()
    items = D.route_items(a.run, tuple(a.teacher_files), stats=stats, dropped=dropped)
    split_of = {it.utterance: it.split for it in items}
    args = [r for r in D.args_rows(a.run, split_of) if r["utterance"] not in dropped]
    data = {k: dict(v) for k, v in stats.items()} | {
        "route_by_label": dict(collections.Counter(x.label for x in items).most_common()),
        "args_dropped_with_route": len(dropped)}
    print(json.dumps(data), flush=True)
    rng = random.Random(a.seed)
    tr_r, va_r = [x for x in items if x.split == "train"], [x for x in items if x.split == "val"]
    tr_a, va_a = [x for x in args if x["split"] == "train"], [x for x in args if x["split"] == "val"]
    if a.limit:
        tr_r = rng.sample(tr_r, min(len(tr_r), round(a.limit * a.route_frac)))
        tr_a = rng.sample(tr_a, min(len(tr_a), a.limit - len(tr_r)))
    full_va_r, full_va_a = va_r, va_a
    va_r, va_a = rng.sample(va_r, min(a.val_route, len(va_r))), rng.sample(va_a, min(a.val_args, len(va_a)))
    gate = check_rows([{"utterance": x.utterance, "rendered_utterance": D.noisy(x.utterance, "r:" + x.utterance, x.split),
                        "split": x.split} for x in tr_r + full_va_r], tr_a + full_va_a)
    hits = {k: v["pairs"] for k, v in gate.items() if k.startswith(("route_", "args_")) and v["pairs"]}
    if hits:  # hard gate: no training or val item may be near any route_v1 / live_t1 utterance
        raise SystemExit(f"evalcheck gate failed: {hits}; affected {gate['affected_counts']}")
    rd, ad = D.route_datums(tr_r, a.model), D.args_datums(tr_a, a.model)
    toks = sum(d.model_input.length for d in rd + ad) * a.epochs
    n_steps = (len(rd) + len(ad)) * a.epochs // a.batch
    n_evals = n_steps // a.eval_every + 1
    rtok = sum(len(render_route(RouteContext(**x.context), x.utterance, a.model).tokens) for x in va_r) / max(len(va_r), 1)
    eval_tok = (n_evals * len(va_r) + (len(full_va_r) if a.final_full_val else 0)) * rtok * (1 + 2 * 0.2) \
        + (n_evals * len(va_a) + (len(full_va_a) if a.final_full_val else 0)) * 250
    est = toks * PRICE_TRAIN / 1e6 + eval_tok * PRICE_PREFILL / 1e6
    cfg = {k: v for k, v in vars(a).items()} | {"train_route": len(rd), "train_args": len(ad), "steps": n_steps,
                                                  "train_tokens": toks, "eval_tokens": int(eval_tok), "est_usd": round(est, 2)}
    print(json.dumps(cfg), flush=True)
    if est > a.max_usd:
        raise SystemExit(f"pre-flight estimate ${est:.2f} exceeds --max-usd {a.max_usd}; aborting")
    if a.dry_run:
        return
    out = OUT / a.name
    out.mkdir(parents=True, exist_ok=True)
    tc = await tinker.ServiceClient().create_lora_training_client_async(base_model=a.model, rank=a.rank, seed=a.seed)
    adam = tinker.AdamParams(learning_rate=a.lr)
    history, ckpts, step = [], [], 0

    async def do_eval():
        client = await tc.save_weights_and_get_sampling_client_async()
        m = await evaluate(client, va_r, va_a, a.model)
        history.append({"step": step, "train_loss": loss, **m})
        print(json.dumps({k: v for k, v in history[-1].items() if k != "per_label"}), flush=True)
        (out / "history.jsonl").write_text("".join(json.dumps(h) + "\n" for h in history))

    loss = float("nan")
    for ep in range(a.epochs):
        for b in D.batches(rd, ad, a.batch, a.route_frac, a.seed + ep, a.mode):
            t0 = time.time()
            fb = await (await tc.forward_backward_async(b, "cross_entropy")).result_async()
            await (await tc.optim_step_async(adam)).result_async()
            m = fb.metrics
            loss = float(m.get("loss:sum", float("nan"))) / max(sum(float(d.loss_fn_inputs["weights"].to_torch().sum()) for d in b), 1.0)
            step += 1
            print(json.dumps({"step": step, "loss": loss, "s": round(time.time() - t0, 1)}), flush=True)
            if step % a.eval_every == 0:
                await do_eval()
            if step % a.save_every == 0:
                p = (await (await tc.save_state_async(f"{a.name}-{step}")).result_async()).path
                ckpts.append({"step": step, "path": p, "kind": "state"})
    await do_eval()
    final = None
    if a.final_full_val:
        final = await evaluate(await tc.save_weights_and_get_sampling_client_async(), full_va_r, full_va_a, a.model)
        (out / "final_eval.json").write_text(json.dumps(final, indent=1))
        print(json.dumps({k: v for k, v in final.items() if not k.startswith("per_label")}), flush=True)
    p = (await (await tc.save_weights_for_sampler_async(f"{a.name}-final")).result_async()).path
    ckpts.append({"step": step, "path": p, "kind": "sampler"})
    p2 = (await (await tc.save_state_async(f"{a.name}-final")).result_async()).path
    ckpts.append({"step": step, "path": p2, "kind": "state"})
    (out / "checkpoints.json").write_text(json.dumps(ckpts, indent=1))
    print(write_report(a.name, cfg, history, ckpts, final, data))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="v2all")
    ap.add_argument("--name", required=True)
    ap.add_argument("--teacher-files", nargs="*", default=[])
    ap.add_argument("--model", default=STUDENT_MODEL)
    ap.add_argument("--limit", type=int, required=True, help="train items (route+args); 0 = all")
    ap.add_argument("--lr", type=float, required=True)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--route-frac", type=float, default=0.6)
    ap.add_argument("--mode", choices=["mixed", "alternate"], default="mixed")
    ap.add_argument("--eval-every", type=int, default=50)
    ap.add_argument("--save-every", type=int, default=200)
    ap.add_argument("--val-route", type=int, default=300)
    ap.add_argument("--val-args", type=int, default=200)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--final-full-val", action="store_true", help="final eval on the whole val split")
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
