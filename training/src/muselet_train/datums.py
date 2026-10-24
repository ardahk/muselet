"""Training data for Phase 1 (SPEC 1.4-1.6): soft route targets + ARGS supervised datums.

Route targets: teacher blend `normalize(0.6*onehot + 0.4*teacher)` where scored, A1 verdicts applied
(see route_items), one-hot elsewhere. ASR noise on 30% of train route items; ARGS items are never noised
(training-16: the copied spans in the target must match the utterance).
"""

from __future__ import annotations

import collections
import json
import random

import tinker
from dataclasses import dataclass

from tinker_cookbook.recipes.decisions.train import decision_dist_datums
from tinker_cookbook.renderers import TrainOnWhat
from tinker_cookbook.supervised.data import conversation_to_datum

from muselet_train import asr
from muselet_train.catalog import option_names, skill_by_name
from muselet_train.gen import DATA, _load
from muselet_train.route_render import RouteContext, args_messages, base_renderer, route_decision, route_renderer
from muselet_train.teacher import blend


@dataclass
class RouteItem:
    utterance: str
    context: dict
    label: str
    target: dict[str, float]
    split: str


def route_items(run: str, teacher_files: tuple[str, ...] = (), stats: dict | None = None,
                dropped: set[str] | None = None) -> list[RouteItem]:
    """Lead rules: ASK is kept only where the A1 adjudicator agreed (verdict keep); for MULTI_STEP and
    REFUSE the A1 label is used when it equals the teacher argmax, otherwise the item is dropped; other
    labels apply A1 keep/relabel/drop as specified. Teacher scores only count if the context matches.
    Iteration 2 (optional files in the run dir): ask_rule.jsonl replaces the A1 ASK rule (keep ASK only when a
    required arg is missing and unnamed, else relabel to nearest_skill; one-hot); finance_check.jsonl reverts
    MULTI_STEP->finance_review relabels that are not one of the four review tasks."""
    scored: dict[tuple[str, str], dict] = {}
    for f in teacher_files:
        for r in _load(run, f):
            scored[(r["utterance"], r["src"])] = r
    names = set(option_names())
    st = stats if stats is not None else {}
    for k in ("ask_dropped", "relabeled", "dropped"):
        st.setdefault(k, collections.Counter())
    rule = {(r["utterance"], r["src"]): r for r in _load(run, "ask_rule.jsonl")}
    fin = {(r["utterance"], r["src"]): r["fits"] for r in _load(run, "finance_check.jsonl")}
    out = []

    def drop(r, why):
        st[why][r["label"]] += 1
        if dropped is not None:
            dropped.add(r["utterance"])

    for r in _load(run, "route_train.jsonl") + _load(run, "route_val.jsonl"):
        t = scored.get((r["utterance"], r["src"]))
        if t and t.get("context") != r["context"]:
            t = None
        adj = (t or {}).get("adjudication") or {}
        verdict, alab = adj.get("verdict"), adj.get("label")
        label = r["label"]
        if label == "ASK" and rule:
            v = rule.get((r["utterance"], r["src"])) or {}
            if v.get("verdict") == "concrete" and v.get("nearest_skill") in names:
                st["relabeled"][f"ASK->{v['nearest_skill']}"] += 1
                label = v["nearest_skill"]
            elif v.get("verdict") != "ask":
                drop(r, "ask_dropped")
                continue
            t = None
        elif label == "ASK":
            if not (r.get("a1_ask_keep") or verdict == "keep"):
                drop(r, "ask_dropped")
                continue
        elif label in ("MULTI_STEP", "REFUSE") and verdict in ("keep", "relabel", "drop"):
            if verdict == "drop" or alab not in names or alab != t["teacher_argmax"]:
                drop(r, "dropped")
                continue
            if alab == "finance_review" and fin.get((r["utterance"], r["src"])) is False:
                st.setdefault("finance_reverted", collections.Counter())[label] += 1
                alab, t = label, None
            if alab != label:
                st["relabeled"][f"{label}->{alab}"] += 1
            label = alab
        elif verdict == "drop":
            drop(r, "dropped")
            continue
        elif verdict == "relabel" and alab in names:
            st["relabeled"][f"{label}->{alab}"] += 1
            label = alab
        target = blend(label, t["teacher_probs"]) if t else {label: 1.0}
        out.append(RouteItem(r["utterance"], r["context"], label, target, r.get("split", "train")))
    return out


def noisy(text: str, key: str, split: str) -> str:
    return asr.noise(text, key) if split == "train" and asr.selected(key) else text


def route_datums(items: list[RouteItem], model: str):
    ex = [(route_decision(RouteContext(**it.context), noisy(it.utterance, "r:" + it.utterance, it.split)), it.target)
          for it in items]
    return [_sparse(d) for d in decision_dist_datums(route_renderer(model), ex)]


def _sparse(d: tinker.Datum) -> tinker.Datum:
    """Tinker requires sparse CSR for (T, K) targets with K > 20; only the answer row is nonzero."""
    return tinker.Datum(model_input=d.model_input, loss_fn_inputs={
        k: tinker.TensorData.from_torch_sparse(v.to_torch()) for k, v in d.loss_fn_inputs.items()})


def args_rows(run: str, split_of: dict[str, str]) -> list[dict]:
    rows = _load(run, "args.jsonl")
    for r in rows:
        r["split"] = split_of.get(r["utterance"], "train")
    return rows


def args_datums(rows: list[dict], model: str):
    rend = base_renderer(model)
    return [conversation_to_datum(
        args_messages(skill_by_name(r["skill"]), RouteContext(**r["context"]),
                      r["utterance"], r["target"]),
        rend, max_length=None, train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE) for r in rows]


def batches(route: list, args: list, batch: int, route_frac: float, seed: int, mode: str):
    """Yield batches of `batch` datums, ~route_frac route. mode=mixed: both kinds in one batch;
    mode=alternate: route-only and args-only batches in the same overall ratio."""
    rng = random.Random(seed)
    route, args = route[:], args[:]
    rng.shuffle(route)
    rng.shuffle(args)
    nr = round(batch * route_frac)
    steps = min(len(route) // nr, len(args) // (batch - nr)) if mode == "mixed" else None
    if mode == "mixed":
        for s in range(steps):
            b = route[s * nr:(s + 1) * nr] + args[s * (batch - nr):(s + 1) * (batch - nr)]
            rng.shuffle(b)
            yield b
        return
    rb = [route[i:i + batch] for i in range(0, len(route) - batch + 1, batch)]
    ab = [args[i:i + batch] for i in range(0, len(args) - batch + 1, batch)]
    i = j = 0
    while i < len(rb) or j < len(ab):
        if j >= len(ab) or (i < len(rb) and i * (1 - route_frac) <= j * route_frac):
            yield rb[i]
            i += 1
        else:
            yield ab[j]
            j += 1


def save_meta(run: str, name: str, meta: dict) -> None:
    (DATA / run / name).write_text(json.dumps(meta, indent=1))
