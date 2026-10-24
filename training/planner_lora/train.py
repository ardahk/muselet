"""Planner LoRA SFT on Tinker: Qwen/Qwen3.5-4B, rank 32, LR 2e-4 cosine, batch 32, assistant-only loss.

Data = common.clean(demos) (gate hits dropped), split 95/5 (seed 0); prompts rendered by brain.planner without the
few-shot block or retrieval. `--dry-run` counts tokens and prints the cost estimate without touching Tinker.
Checkpoints (sampler weights, kept) every 25% of the run; at each one: dev loss (forward) and greedy dev samples
graded by evals/planner_offline.grade. Spend guard: abort the launch if month-to-date (max of tools/tinker_spend.py
and --console-mtd) >= --launch-cap; skip sampling once the running estimate reaches --sample-cap.

uv run --project ml --with "mlx[cpu]==0.32.4" python training/planner_lora/train.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

TRAIN_PER_M, PREFILL_PER_M, SAMPLE_PER_M = 0.78, 0.33, 1.0
REPORTS = C.REPO / "training" / "reports"


def api_mtd() -> float:
    out = subprocess.run([sys.executable, str(C.REPO / "tools" / "tinker_spend.py")], capture_output=True, text=True,
                         check=True, cwd=C.REPO).stdout
    return float(json.loads(out[out.index("{"):])["month_to_date_usd"])


def estimate(tr: list[dict], dev: list[dict], epochs: int, n_evals: int) -> dict:
    tt = sum(len(r["tokens"]) for r in tr) * epochs
    dt = sum(len(r["tokens"]) for r in dev)
    dp = sum(r["n_prompt"] for r in dev)
    per_eval = dt / 1e6 * TRAIN_PER_M + dp / 1e6 * PREFILL_PER_M + len(dev) * 64 / 1e6 * SAMPLE_PER_M
    return {"epochs": epochs, "train_tokens": tt, "dev_tokens": dt, "train_usd": round(tt / 1e6 * TRAIN_PER_M, 3),
            "eval_usd_each": round(per_eval, 3), "evals": n_evals,
            "total_usd": round(tt / 1e6 * TRAIN_PER_M + n_evals * per_eval, 3)}


def datum(r: dict):
    import tinker
    import torch
    t = r["tokens"]
    return tinker.Datum(model_input=tinker.ModelInput.from_ints(t[:-1]), loss_fn_inputs={
        "target_tokens": tinker.TensorData.from_torch(torch.tensor(t[1:], dtype=torch.int64)),
        "weights": tinker.TensorData.from_torch(torch.tensor(r["weights"][1:], dtype=torch.float32))})


def loss_of(fb, batch) -> tuple[float, float]:
    """(sum of weighted NLL, sum of weights) for one forward/forward_backward result."""
    import torch
    nll = sum(float(-(o["logprobs"].to_torch() * d.loss_fn_inputs["weights"].to_torch()).sum())
              for o, d in zip(fb.loss_fn_outputs, batch))
    return nll, sum(float(d.loss_fn_inputs["weights"].to_torch().sum()) for d in batch)


async def evaluate(tc, sampler, dev_demos, dev_rows, planner, sample: bool) -> dict:
    import tinker
    nll = w = 0.0
    dd = [datum(r) for r in dev_rows]
    for i in range(0, len(dd), 32):
        a, b = loss_of(await (await tc.forward_async(dd[i:i + 32], "cross_entropy")).result_async(), dd[i:i + 32])
        nll, w = nll + a, w + b
    out = {"dev_loss": round(nll / w, 4)}
    if not sample:
        return out
    im_end = planner.tokenizer.convert_tokens_to_ids("<|im_end|>")
    sem = asyncio.Semaphore(32)

    async def one(d, r):
        async with sem:
            res = await sampler.sample_async(
                prompt=tinker.ModelInput.from_ints(r["tokens"][:r["n_prompt"]]), num_samples=1,
                sampling_params=tinker.SamplingParams(max_tokens=320, temperature=0.0, stop=[im_end]))
        toks = [t for t in res.sequences[0].tokens if t != im_end]
        text = planner.tokenizer.decode(toks)
        g = C.grade(d["state"], C.to_lines(text))
        return {"id": d["id"], "category": d["category"], "pass": bool(g["pass"]), "strict": bool(g["strict_pass"]),
                "valid": bool(g["valid"]), "text": text}

    rows = await asyncio.gather(*(one(d, r) for d, r in zip(dev_demos, dev_rows)))
    n = len(rows)
    return {**out, "dev_pass": round(sum(x["pass"] for x in rows) / n, 4),
            "dev_strict": round(sum(x["strict"] for x in rows) / n, 4),
            "dev_valid": round(sum(x["valid"] for x in rows) / n, 4), "samples": rows}


async def run(a, tr_d, dev_d, tr, dev, planner, est) -> dict:
    import tinker
    steps_per_epoch = math.ceil(len(tr) / a.batch)
    total = steps_per_epoch * a.epochs
    ckpt_at = sorted({math.ceil(total * q / 4) for q in (1, 2, 3, 4)})
    svc = tinker.ServiceClient()
    tc = await svc.create_lora_training_client_async(base_model=C.BASE_MODEL, rank=a.rank, seed=a.seed)
    spent, base = 0.0, a.mtd
    log = {"args": vars(a), "estimate": est, "steps": total, "ckpt_at": ckpt_at, "train": [], "ckpts": []}
    out = REPORTS / f"{a.name}.json"

    def save():
        out.write_text(json.dumps(log, indent=1))

    async def checkpoint(step: int):
        nonlocal spent
        p = (await (await tc.save_weights_for_sampler_async(f"{a.name}-{step:04d}")).result_async()).path
        can_sample = base + spent + est["eval_usd_each"] < a.sample_cap
        sampler = await svc.create_sampling_client_async(model_path=p) if can_sample else None
        ev = await evaluate(tc, sampler, dev_d, dev, planner, can_sample)
        spent += est["eval_usd_each"]
        log["ckpts"].append({"step": step, "epoch": round(step / steps_per_epoch, 3), "path": p,
                             **{k: v for k, v in ev.items() if k != "samples"}})
        (REPORTS / f"{a.name}-dev-{step:04d}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in ev.get("samples", [])))
        print("ckpt", log["ckpts"][-1], flush=True)
        save()

    if a.eval_base:
        sampler = await svc.create_sampling_client_async(base_model=C.BASE_MODEL)
        ev = await evaluate(tc, sampler, dev_d, dev, planner, True)
        spent += est["eval_usd_each"]
        log["base"] = {k: v for k, v in ev.items() if k != "samples"}
        (REPORTS / f"{a.name}-dev-base.jsonl").write_text("".join(json.dumps(x) + "\n" for x in ev["samples"]))
        print("base", log["base"], flush=True)
    rng = random.Random(a.seed)
    step = 0
    for ep in range(a.epochs):
        order = list(range(len(tr)))
        rng.shuffle(order)
        for i in range(0, len(order), a.batch):
            batch = [datum(tr[j]) for j in order[i:i + a.batch]]
            lr = a.lr * 0.5 * (1 + math.cos(math.pi * step / total))
            t0 = time.time()
            fb = await (await tc.forward_backward_async(batch, "cross_entropy")).result_async()
            await (await tc.optim_step_async(tinker.AdamParams(learning_rate=lr))).result_async()
            step += 1
            nll, w = loss_of(fb, batch)
            spent += sum(len(tr[j]["tokens"]) for j in order[i:i + a.batch]) / 1e6 * TRAIN_PER_M
            log["train"].append({"step": step, "lr": lr, "loss": round(nll / w, 4), "s": round(time.time() - t0, 1)})
            print(f"step {step}/{total} ep {ep} lr {lr:.2e} loss {nll / w:.4f} spent~${spent:.2f}", flush=True)
            if step in ckpt_at:
                await checkpoint(step)
    log["spent_estimate_usd"] = round(spent, 3)
    save()
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demos", default=None, help="local demos.jsonl.gz (default: HF @ pinned revision)")
    ap.add_argument("--name", default="planner-lora-v1")
    ap.add_argument("--epochs", type=int, default=0, help="0 = 2 if the lane fits --lane-usd, else 1")
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lane-usd", type=float, default=7.0)
    ap.add_argument("--console-mtd", type=float, default=None, help="latest month-to-date seen on the Tinker console")
    ap.add_argument("--launch-cap", type=float, default=142.0)
    ap.add_argument("--sample-cap", type=float, default=146.0)
    ap.add_argument("--eval-base", action="store_true", help="also grade the untrained base on dev (reference)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    demos, rep = C.clean(C.load_demos(a.demos))
    tr_d, dev_d = C.split(demos)
    planner = C.make_planner()
    tr = [C.render(planner, d["state"], d["completion"]) for d in tr_d]
    dev = [C.render(planner, d["state"], d["completion"]) for d in dev_d]
    n_evals = 4 + a.eval_base
    est = {e: estimate(tr, dev, e, n_evals) for e in (1, 2)}
    a.epochs = a.epochs or (2 if est[2]["total_usd"] <= a.lane_usd else 1)
    summary = {"demos_in": len(demos) + len({p["id"] for p in rep["pairs"]}), "gate_dropped":
               sorted({p["id"] for p in rep["pairs"]}), "train": len(tr), "dev": len(dev),
               "gate_hits_before_drop": rep["hits"], "eval_items": rep["eval_items"], "estimate": est,
               "epochs": a.epochs, "steps": math.ceil(len(tr) / a.batch) * a.epochs,
               "mean_prompt_tokens": round(sum(r["n_prompt"] for r in tr) / len(tr), 1),
               "mean_target_tokens": round(sum(len(r["tokens"]) - r["n_prompt"] for r in tr) / len(tr), 1)}
    print(json.dumps(summary, indent=1))
    (REPORTS / f"{a.name}-dryrun.json").write_text(json.dumps(summary, indent=1))
    if C.gate_report(demos)["pairs"]:
        raise SystemExit("gate not clean after drop")
    if a.dry_run:
        return
    if a.console_mtd is None:
        raise SystemExit("pass --console-mtd (the API lags by hours)")
    a.mtd = max(api_mtd(), a.console_mtd)
    if a.mtd >= a.launch_cap or a.mtd + est[a.epochs]["total_usd"] >= 148.0:
        raise SystemExit(f"spend guard: month-to-date ${a.mtd:.2f} (+${est[a.epochs]['total_usd']:.2f})")
    print(f"launch: month-to-date ${a.mtd:.2f}, estimate ${est[a.epochs]['total_usd']:.2f}", flush=True)
    log = asyncio.run(run(a, tr_d, dev_d, tr, dev, planner, est[a.epochs]))
    print(json.dumps({k: log[k] for k in ("ckpts", "spent_estimate_usd")}, indent=1))


if __name__ == "__main__":
    main()
