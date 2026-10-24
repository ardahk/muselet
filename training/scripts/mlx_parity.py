# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "mlx[cpu]==0.32.4",
#   "mlx-lm==0.32.2",
#   "transformers==5.20.1",
#   "huggingface_hub==2.2.0",
# ]
# ///
"""MLX export + CPU route parity (separate env: mlx-lm needs transformers>=5.7, the project pins 5.5.4).

  uv run --script training/scripts/mlx_parity.py convert --hf DIR --out DIR [--bits 4]
  uv run --script training/scripts/mlx_parity.py parity --mlx DIR --parity parity.jsonl [--n 300]

parity.jsonl rows (from muselet_train.export): tokens (full route prompt incl. answer placeholder),
choice_pos, label_tokens {label: id}, probs {label: p} from the Tinker sampler.
"""

import argparse
import copy
import json
import os
import time

import mlx.core as mx


def convert(a):
    from mlx_lm import convert as cv
    cv(a.hf, mlx_path=a.out, quantize=True, q_bits=a.bits, q_group_size=64)


def parity(a):
    from mlx_lm import load
    from mlx_lm.models.cache import make_prompt_cache
    model, _ = load(a.mlx)
    rows = [json.loads(x) for x in open(a.parity) if x.strip()][: a.n]
    # static system prefix is shared by every row: prefill it once and copy the cache per row
    seqs = [r["tokens"][: r["choice_pos"]] for r in rows]
    k = len(os.path.commonprefix(seqs)) - 1
    base = make_prompt_cache(model)
    model(mx.array([seqs[0][:k]]), cache=base)
    mx.eval([c.state for c in base])
    agree, dmax, dsum, t0 = 0, 0.0, 0.0, time.time()
    worst = []
    for r in rows:
        labels = list(r["probs"])
        ids = mx.array([r["label_tokens"][k] for k in labels])
        logits = model(mx.array([r["tokens"][k: r["choice_pos"]]]), cache=copy.deepcopy(base))[0, -1]
        p = mx.softmax(logits[ids].astype(mx.float32)).tolist()
        q = [r["probs"][k] for k in labels]
        d = max(abs(x - y) for x, y in zip(p, q))
        agree += max(range(len(p)), key=p.__getitem__) == max(range(len(q)), key=q.__getitem__)
        dmax, dsum = max(dmax, d), dsum + d
        worst.append((d, r.get("utterance", ""), labels[max(range(len(p)), key=p.__getitem__)],
                      labels[max(range(len(q)), key=q.__getitem__)]))
    n = len(rows)
    out = {"n": n, "shared_prefix_tokens": k, "argmax_agreement": agree / n, "max_abs_dp": dmax, "mean_max_abs_dp": dsum / n,
           "sec_per_item": (time.time() - t0) / n, "worst": sorted(worst, reverse=True)[:10]}
    print(json.dumps(out, indent=1))
    if a.report:
        open(a.report, "w").write(json.dumps(out, indent=1))


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
c = sub.add_parser("convert")
c.add_argument("--hf", required=True)
c.add_argument("--out", required=True)
c.add_argument("--bits", type=int, default=4)
p = sub.add_parser("parity")
p.add_argument("--mlx", required=True)
p.add_argument("--parity", required=True)
p.add_argument("--n", type=int, default=300)
p.add_argument("--report")
a = ap.parse_args()
{"convert": convert, "parity": parity}[a.cmd](a)
