#!/usr/bin/env python3
"""M0 speed lab: measure on-device latency of candidate models on this Mac.

Text models (mlx-lm):
  cold      full prompt prefilled from an empty cache            -> prefill tok/s
  cached    static prefix cached once, deep-copied per request,
            only the dynamic suffix is prefilled; logits for the
            last position only (= one typed decision)             -> decision latency
  decode    greedy decode after the cached suffix                -> decode tok/s

Vision models (mlx-vlm): time-to-first-token for one screenshot at several resolutions.

Usage:
  uv run --project ml python bench/speed_lab.py --models mlx-community/Qwen3.5-4B-4bit
  uv run --project ml python bench/speed_lab.py --vlm-models deskmind/eyes-4b-mlx-4bit
"""

import argparse
import copy
import gc
import json
import platform
import statistics
import time
from pathlib import Path

import mlx.core as mx

SHAPES = {
    "route": dict(prefix=1500, suffix=60, decode=0),
    "decide": dict(prefix=1500, suffix=400, decode=0),
    "plan": dict(prefix=3000, suffix=800, decode=128),
    "cold4k": dict(prefix=0, suffix=4096, decode=32),
}

SKILLS = [
    ("set_volume", "level:int 0-100", "Set the system output volume."),
    ("mute", "on:bool", "Mute or unmute system audio."),
    ("set_brightness", "level:int 0-100", "Set the built-in display brightness."),
    ("dark_mode", "on:bool", "Switch macOS appearance between dark and light."),
    ("open_app", "name:str", "Launch or focus an application by name."),
    ("quit_app", "name:str", "Quit a running application."),
    ("open_url", "url:str", "Open a URL in the default browser."),
    ("web_search", "query:str", "Search the web for a query."),
    ("create_event", "title:str start:datetime end:datetime", "Create a Calendar event."),
    ("create_reminder", "title:str due:datetime?", "Create a Reminders item."),
    ("start_timer", "seconds:int label:str?", "Start a countdown timer."),
    ("take_screenshot", "region:enum[full,window,selection]", "Capture the screen to Desktop."),
    ("new_note", "title:str body:str", "Create a note in Notes."),
    ("find_file", "query:str", "Search files with Spotlight."),
    ("move_file", "src:path dst:path", "Move a file in Finder."),
    ("new_folder", "parent:path name:str", "Create a folder."),
    ("send_message", "to:contact body:str", "Send an iMessage (requires confirmation)."),
    ("play_music", "query:str?", "Play music in the Music app."),
    ("set_focus", "mode:str on:bool", "Turn a Focus mode on or off."),
    ("wifi", "on:bool", "Turn Wi-Fi on or off."),
    ("premiere_cut", "time:timecode", "Razor-cut the active Premiere Pro sequence at a time."),
    ("premiere_export", "preset:str", "Export the active Premiere Pro sequence."),
    ("click_element", "id:int", "Press the numbered UI element."),
    ("type_text", "id:int text:str", "Type text into the numbered field."),
    ("press_keys", "combo:str", "Press a keyboard shortcut."),
    ("scroll", "id:int direction:enum[up,down]", "Scroll the numbered container."),
    ("multi_step", "", "The request needs a multi-step plan."),
    ("ask_user", "question:str", "The request is ambiguous; ask a clarifying question."),
    ("refuse", "reason:str", "The request is impossible offline or unsafe."),
]

ROLES = ["AXButton", "AXTextField", "AXStaticText", "AXCheckBox", "AXMenuItem", "AXRow", "AXLink", "AXPopUpButton"]
LABELS = ["Save", "Cancel", "Search", "Subject", "To", "Send", "Bold", "Font size", "Export", "Timeline",
          "Inbox", "New Folder", "Downloads", "Share", "Settings", "Volume", "Display", "Close tab"]


def prefix_text():
    lines = ["You are the decision core of an on-device macOS agent. Choose exactly one option.",
             "Rules: prefer native skills; ask when ambiguous; refuse unsafe or impossible requests.",
             "Available skills:"]
    i = 0
    while len(lines) < 4000:
        name, args, desc = SKILLS[i % len(SKILLS)]
        lines.append(f"- {name}_{i // len(SKILLS)}({args}): {desc}")
        i += 1
    return "\n".join(lines)


def suffix_text():
    lines = ["User said: \"turn the volume down to thirty and then open my downloads folder in finder\"",
             "Frontmost app: Finder. Focused window: \"Recents\". Accessibility tree:"]
    i = 0
    while len(lines) < 4000:
        role, label = ROLES[i % len(ROLES)], LABELS[(i * 7) % len(LABELS)]
        lines.append(f"[{i}] {role} \"{label} {i}\" @({(i * 37) % 1440},{(i * 53) % 900},{80 + i % 40},{22})")
        i += 1
    return "\n".join(lines)


def exact_tokens(tokenizer, text, n):
    ids = tokenizer.encode(text)
    while len(ids) < n:
        ids = ids + ids
    return ids[:n]


def mem(name):
    f = getattr(mx, name, None) or getattr(mx.metal, name, None)
    return f


def gb(x):
    return round(x / 1e9, 3)


def stats(xs):
    xs = sorted(xs)
    return dict(median=round(statistics.median(xs), 2), min=round(xs[0], 2), max=round(xs[-1], 2), n=len(xs))


def split_model(model):
    lm = getattr(model, "language_model", model)
    body = lm.model
    args = getattr(lm, "args", None)
    tied = bool(getattr(args, "tie_word_embeddings", False)) or not hasattr(lm, "lm_head")
    head = body.embed_tokens.as_linear if tied else lm.lm_head
    return body, head


def prefill(body, head, ids, cache, step=2048, eval_cache=False):
    toks = mx.array(ids)[None]
    n, i = toks.shape[1], 0
    while n - i > step:
        body(toks[:, i:i + step], cache=cache)
        mx.eval([c.state for c in cache])
        i += step
    h = body(toks[:, i:], cache=cache)
    logits = head(h[:, -1:, :])
    if eval_cache:
        mx.eval(logits, [c.state for c in cache])
    else:
        mx.eval(logits)
    return logits


def decode(body, head, logits, cache, n):
    y = mx.argmax(logits[:, -1, :], axis=-1)
    mx.eval(y)
    t0 = time.perf_counter()
    for _ in range(n):
        h = body(y[:, None], cache=cache)
        y = mx.argmax(head(h[:, -1:, :])[:, -1, :], axis=-1)
        mx.async_eval(y)
    mx.eval(y)
    return n / (time.perf_counter() - t0)


def bench_text(repo, shapes, runs):
    from mlx_lm import load
    from mlx_lm.models.cache import make_prompt_cache

    mem("reset_peak_memory")()
    t0 = time.perf_counter()
    model, tokenizer = load(repo)
    load_s = time.perf_counter() - t0
    weights_gb = gb(mem("get_active_memory")())
    body, head = split_model(model)
    pre_txt, suf_txt = prefix_text(), suffix_text()

    warm = exact_tokens(tokenizer, pre_txt, 256)
    for _ in range(2):
        prefill(body, head, warm, make_prompt_cache(model), eval_cache=True)

    out = dict(model=repo, kind="text", load_s=round(load_s, 2), weights_gb=weights_gb, shapes={})
    for name in shapes:
        s = SHAPES[name]
        pre = exact_tokens(tokenizer, pre_txt, s["prefix"]) if s["prefix"] else []
        suf = exact_tokens(tokenizer, suf_txt, s["suffix"])
        full = pre + suf
        r = dict(prefix_tokens=len(pre), suffix_tokens=len(suf))

        cold = []
        for _ in range(runs):
            c = make_prompt_cache(model)
            t = time.perf_counter()
            prefill(body, head, full, c)
            cold.append((time.perf_counter() - t) * 1000)
            del c
        r["cold_ms"] = stats(cold)
        r["cold_prefill_tok_s"] = round(len(full) / (r["cold_ms"]["median"] / 1000), 1)

        if pre:
            base = make_prompt_cache(model)
            t = time.perf_counter()
            prefill(body, head, pre, base, eval_cache=True)
            r["prefix_build_ms"] = round((time.perf_counter() - t) * 1000, 2)
            copy_ms, suf_ms = [], []
            for _ in range(runs):
                t = time.perf_counter()
                c = copy.deepcopy(base)
                mx.eval([x.state for x in c])
                t1 = time.perf_counter()
                prefill(body, head, suf, c)
                t2 = time.perf_counter()
                copy_ms.append((t1 - t) * 1000)
                suf_ms.append((t2 - t1) * 1000)
                del c
            r["snapshot_copy_ms"] = stats(copy_ms)
            r["cached_suffix_ms"] = stats(suf_ms)
            r["cached_total_ms_median"] = round(r["snapshot_copy_ms"]["median"] + r["cached_suffix_ms"]["median"], 2)
            r["suffix_prefill_tok_s"] = round(len(suf) / (r["cached_suffix_ms"]["median"] / 1000), 1)

        if s["decode"]:
            tps = []
            for _ in range(max(2, runs // 2)):
                c = make_prompt_cache(model)
                logits = prefill(body, head, full, c, eval_cache=True)
                tps.append(decode(body, head, logits, c, s["decode"]))
                del c
            r["decode_tok_s"] = stats(tps)
        out["shapes"][name] = r
        print(json.dumps({name: r}), flush=True)

    out["peak_gb"] = gb(mem("get_peak_memory")())
    del model, tokenizer, body, head
    gc.collect()
    mem("clear_cache")()
    return out


def synthetic_screenshot(w, h, path):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), (236, 236, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 28], fill=(220, 220, 220))
    for i in range(int(w * h / 9000)):
        x, y = (i * 97) % (w - 160), 40 + (i * 61) % (h - 70)
        d.rectangle([x, y, x + 120, y + 24], outline=(120, 120, 120), fill=(250, 250, 250))
        d.text((x + 6, y + 6), f"{LABELS[i % len(LABELS)]} {i}", fill=(20, 20, 20))
    img.save(path)
    return path


def bench_vlm(repo, sizes, runs, tmp):
    from mlx_vlm import generate, load
    from mlx_vlm.prompt_utils import apply_chat_template

    mem("reset_peak_memory")()
    t0 = time.perf_counter()
    model, processor = load(repo)
    load_s = time.perf_counter() - t0
    weights_gb = gb(mem("get_active_memory")())
    prompt = apply_chat_template(processor, model.config,
                                 "Click the 'Export' button. Answer with the element center as (x, y) in pixels.",
                                 num_images=1)
    out = dict(model=repo, kind="vlm", load_s=round(load_s, 2), weights_gb=weights_gb, sizes={})
    for size in sizes:
        w, h = map(int, size.split("x"))
        img = synthetic_screenshot(w, h, str(tmp / f"shot_{w}x{h}.png"))
        generate(model, processor, prompt, image=[img], max_tokens=1, verbose=False)
        ttft = []
        res = None
        for _ in range(runs):
            t = time.perf_counter()
            res = generate(model, processor, prompt, image=[img], max_tokens=1, verbose=False)
            ttft.append((time.perf_counter() - t) * 1000)
        dec = generate(model, processor, prompt, image=[img], max_tokens=64, verbose=False)
        r = dict(ttft_ms=stats(ttft),
                 prompt_tokens=getattr(res, "prompt_tokens", None),
                 prompt_tok_s=round(getattr(res, "prompt_tps", 0) or 0, 1),
                 decode_tok_s=round(getattr(dec, "generation_tps", 0) or 0, 1))
        out["sizes"][size] = r
        print(json.dumps({size: r}), flush=True)
    out["peak_gb"] = gb(mem("get_peak_memory")())
    del model, processor
    gc.collect()
    mem("clear_cache")()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--vlm-models", nargs="*", default=[])
    ap.add_argument("--shapes", default="route,decide,plan,cold4k")
    ap.add_argument("--image-sizes", default="1280x800,1920x1200,2560x1600")
    ap.add_argument("--runs", type=int, default=7)
    ap.add_argument("--out", default="runs/speedlab/results.jsonl")
    a = ap.parse_args()

    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    env = dict(mlx=mx.__version__, machine=platform.machine(), macos=platform.mac_ver()[0])
    try:
        env["device"] = (getattr(mx, "device_info", None) or mx.metal.device_info)()
    except Exception as e:
        env["device"] = str(e)

    results = []
    for repo in a.models:
        try:
            results.append(bench_text(repo, a.shapes.split(","), a.runs))
        except Exception as e:
            results.append(dict(model=repo, kind="text", error=repr(e)))
            print(f"ERROR {repo}: {e!r}", flush=True)
    for repo in a.vlm_models:
        try:
            results.append(bench_vlm(repo, a.image_sizes.split(","), a.runs, outp.parent))
        except Exception as e:
            results.append(dict(model=repo, kind="vlm", error=repr(e)))
            print(f"ERROR {repo}: {e!r}", flush=True)

    with outp.open("a") as f:
        for r in results:
            r["env"] = env
            r["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            f.write(json.dumps(r, default=str) + "\n")
    print(f"wrote {len(results)} results to {outp}")


if __name__ == "__main__":
    main()
