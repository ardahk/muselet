"""Write training/artifacts/route_render_samples.jsonl (id list + 50 rendered route examples)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from muselet_train.catalog import options, render_samples_path, skills
from muselet_train.contexts import sample_context
from muselet_train.route_render import (
    PLACEHOLDER,
    PREFIX,
    STUDENT_MODEL,
    render_route,
    route_renderer,
)

OUT = render_samples_path()
SPECIAL_EXAMPLES = {
    "MULTI_STEP": ["open safari, search flights to tokyo and sort by price",
                   "in premiere add a cross dissolve between the first two clips",
                   "fill in the total column with a sum formula"],
    "ASK": ["set a timer", "text him", "open that file"],
    "REFUSE": ["read my partner's messages without them knowing", "make my laptop fly"],
    "ANSWER": ["what's 15 percent of 80", "what does command shift 4 do"],
}


def main(out: Path = OUT, n: int = 50, seed: int = 0) -> None:
    rng = random.Random(seed)
    rr = route_renderer()
    tok = rr.tokenizer
    cr = rr.choice_renderer
    names = [o.name for o in options()]
    pool = [(o.name, ex) for o in skills() for ex in o.examples]
    pool += [(k, ex) for k, v in SPECIAL_EXAMPLES.items() for ex in v]
    rng.shuffle(pool)
    items = pool[:n]
    header = {
        "kind": "header",
        "model": STUDENT_MODEL,
        "renderer": rr.renderer.__class__.__name__,
        "prefix": PREFIX,
        "prefix_tokens": tok.encode(PREFIX, add_special_tokens=False),
        "placeholder": PLACEHOLDER,
        "placeholder_token": cr.answer_tokens[-1],
        "id_alphabet": "".join(cr.ids),
        "id_tokens": {c: cr.id_tokens[c] for c in cr.ids},
        "options": [{"id": cr.id_for(i), "name": nm, "token": cr.id_tokens[cr.id_for(i)]}
                    for i, nm in enumerate(names)],
    }
    lines = [header]
    for i, (label, utt) in enumerate(items):
        ctx = sample_context(rng)
        r = render_route(ctx, utt)
        lines.append({
            "kind": "route", "i": i, "utterance": utt, "label": label,
            "context": ctx.__dict__, "choice_pos": r.choice_pos, "n_tokens": len(r.tokens),
            "label_token": r.label_tokens[label], "tokens": r.tokens,
            "text": tok.decode(r.tokens),
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
    print(f"wrote {out} ({out.stat().st_size} bytes); ids={header['id_alphabet']}")


if __name__ == "__main__":
    main()
