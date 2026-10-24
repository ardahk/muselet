"""Retrieval and rendering for solved planner demonstrations."""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX_OBS_LINES = 12
STOP = {"app", "window", "focused", "none", "the", "a", "an", "to", "my",
        "in", "on", "of", "and", "for", "this", "is", "it", "me"}
REQUIRED_FIELDS = ("goal", "app", "category", "obs_header", "batch")


@dataclass
class Demo:
    goal: str
    app: str
    category: str
    obs_header: str
    batch: list[str]
    id: str | None = None
    obs_lines: list[str] = field(default_factory=list)
    last_batch: list[str] | None = None
    script_output: str | None = None
    source: str = ""


def normalize(goal: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", goal.lower()).split()).strip()


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower())
            if not token.isdigit() and token not in STOP]


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    if j < len(b) or i < len(a):
        edits += 1
    return edits <= 1


def is_leak(a: str, b: str, n: int = 13) -> bool:
    """Whether normalized goals share a long word run or are one edit apart."""
    a, b = normalize(a), normalize(b)
    aw, bw = a.split(), b.split()
    if len(aw) >= n and len(bw) >= n:
        grams = {tuple(aw[i:i + n]) for i in range(len(aw) - n + 1)}
        if any(tuple(bw[i:i + n]) in grams for i in range(len(bw) - n + 1)):
            return True
    return _edit_distance_at_most_one(a, b)


def _scenario_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _app_from_header(header: str) -> str:
    match = re.search(r"\bapp:\s*(.*?)\s*\|", header)
    return match.group(1).strip() if match else ""


def from_v2_scenarios(path=ROOT / "evals" / "planner_scenarios_v2.jsonl") -> list[Demo]:
    demos = []
    for row in _scenario_rows(Path(path)):
        if row.get("split") != "v2-tune":
            continue
        observation_lines = row["observation"].splitlines()
        if not observation_lines:
            header = ""
            content_lines = []
        else:
            header = observation_lines[0]
            content_lines = observation_lines[1:]
        batch = row["gold"][0]
        refs = set(re.findall(r"#(\d+)", "\n".join(batch + (row.get("last_batch") or []))))
        focused = re.search(r"\bfocused:\s*#(\d+)", header)
        if focused:
            refs.add(focused.group(1))
        elements = []
        other_lines = []
        for index, line in enumerate(content_lines):
            if not line.strip() or line.startswith("#") and not re.match(r"^#\d+\b", line):
                continue
            element = re.match(r"^#(\d+)\b", line)
            if element:
                elements.append((index, element.group(1), line))
            else:
                other_lines.append((index, line))

        required = [(index, ref, line) for index, ref, line in elements if ref in refs]
        if len(required) > MAX_OBS_LINES:
            raise ValueError(f"{row.get('id', '<unknown>')}: more than {MAX_OBS_LINES} referenced observation lines")
        chosen = {index for index, _, _ in required}
        room = MAX_OBS_LINES - len(chosen)
        for index, _ in other_lines:
            if room <= 0:
                break
            chosen.add(index)
            room -= 1
        for index, _, _ in elements:
            if room <= 0:
                break
            if index not in chosen:
                chosen.add(index)
                room -= 1
        obs_lines = [line for index, line in enumerate(content_lines) if index in chosen]
        demos.append(Demo(
            id=row.get("id"),
            goal=row["goal"],
            app=_app_from_header(header),
            category=row["category"],
            obs_header=header,
            obs_lines=obs_lines,
            batch=batch,
            last_batch=row.get("last_batch"),
            script_output=row.get("script_output"),
            source="v2-tune",
        ))
    return demos


def load_jsonl(path) -> list[Demo]:
    demos = []
    for line_number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = [name for name in REQUIRED_FIELDS if name not in row]
        if missing:
            raise ValueError(f"line {line_number}: missing required field(s): {', '.join(missing)}")
        fields = Demo.__dataclass_fields__
        demos.append(Demo(**{name: row[name] for name in fields if name in row}))
    return demos


@lru_cache(maxsize=1)
def denylist() -> tuple[set[str], list[str]]:
    """Load the complete set of frozen evaluation prompts and identifiers."""
    import importlib.util

    offline_path = ROOT / "evals" / "planner_offline.py"
    live_path = ROOT / "evals" / "live_t1.jsonl"
    external_path = ROOT / "evals" / "external" / "utterances.jsonl"
    v2_path = ROOT / "evals" / "planner_scenarios_v2.jsonl"
    for source in (offline_path, live_path, external_path, v2_path):
        if not source.is_file():
            raise FileNotFoundError(source)
    spec = importlib.util.spec_from_file_location("_planner_offline_for_denylist", offline_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {offline_path}")
    offline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(offline)
    ids: set[str] = set()
    goals: list[str] = []

    for scenario in offline.TUNE + offline.HOLDOUT + offline.HOLDOUT2:
        if scenario.get("id"):
            ids.add(scenario["id"])
        if scenario.get("goal"):
            goals.append(normalize(scenario["goal"]))

    for row in _scenario_rows(v2_path):
        if row.get("split") == "v2-holdout":
            if row.get("id"):
                ids.add(row["id"])
            if row.get("goal"):
                goals.append(normalize(row["goal"]))

    for row in _scenario_rows(live_path):
        if row.get("id"):
            ids.add(row["id"])
        if row.get("utterance"):
            goals.append(normalize(row["utterance"]))

    for row in _scenario_rows(external_path):
        if row.get("id"):
            ids.add(row["id"])
        if row.get("text"):
            goals.append(normalize(row["text"]))
    return ids, goals


def _filter_demos(demos: list[Demo], denied=None) -> tuple[list[Demo], dict[str, int]]:
    ids, goals = denied if denied is not None else denylist()
    goal_set = set(goals)
    by_length: dict[int, list[str]] = defaultdict(list)
    for goal in goal_set:
        by_length[len(goal)].append(goal)
    kept, dropped = [], Counter()
    for demo in demos:
        normalized = normalize(demo.goal)
        if demo.id and demo.id in ids:
            dropped["id"] += 1
            continue
        if normalized in goal_set:
            dropped["goal"] += 1
            continue
        candidates = (candidate for length in range(len(normalized) - 1, len(normalized) + 2)
                      for candidate in by_length.get(length, ()))
        if any(is_leak(normalized, candidate) for candidate in candidates):
            dropped["leak"] += 1
            continue
        kept.append(demo)
    return kept, {"total": sum(dropped.values()), "id": dropped["id"],
                  "goal": dropped["goal"], "leak": dropped["leak"]}


def load_bank(spec: str = "v2-tune") -> list[Demo]:
    if spec == "v2-tune":
        demos = from_v2_scenarios()
    elif spec == "hf" or spec.startswith("hf:"):
        parts = spec.split(":", 2)
        repo = parts[1] if len(parts) > 1 and parts[1] else "jonsnov/muselet-planner-demos-v1"
        filename = parts[2] if len(parts) > 2 and parts[2] else "bank.jsonl"
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(repo_id=repo, filename=filename, repo_type="dataset")
        demos = load_jsonl(downloaded)
    else:
        demos = load_jsonl(spec)
    filtered, stats = _filter_demos(demos)
    load_bank.last_dropped = stats
    return filtered


load_bank.last_dropped = {"total": 0, "id": 0, "goal": 0, "leak": 0}


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.doc_lens = [len(doc) for doc in docs]
        self.avgdl = sum(self.doc_lens) / self.n if self.n else 0.0
        self.term_freqs = [Counter(doc) for doc in docs]
        df = Counter(token for frequencies in self.term_freqs for token in frequencies)
        self.idf = {term: math.log(1 + (self.n - count + 0.5) / (count + 0.5))
                    for term, count in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        scores = []
        for frequencies, length in zip(self.term_freqs, self.doc_lens):
            score = 0.0
            for term in query_tokens:
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                norm = tf + self.k1 * (1 - self.b + self.b * length / self.avgdl) if self.avgdl else tf
                score += self.idf[term] * tf * (self.k1 + 1) / norm
            scores.append(score)
        return scores


class PlanBank:
    def __init__(self, demos: list[Demo]):
        self.demos = demos
        docs = [tokenize(d.goal) + tokenize(d.app) + tokenize(d.obs_header) for d in demos]
        self.bm25 = BM25(docs)

    def retrieve(self, goal: str, observation: str, k: int) -> list[Demo]:
        if k == 0:
            return []
        lines = observation.splitlines()
        header = next((line for line in lines if line.strip().startswith("app:")),
                      lines[0] if lines else "")
        query = tokenize(goal) + tokenize(_app_from_header(header)) + tokenize(header)
        scores = self.bm25.scores(query)
        ranked = sorted(enumerate(scores), key=lambda item: (-item[1], item[0]))
        selected, seen = [], set()
        for index, score in ranked:
            if score <= 0:
                continue
            demo = self.demos[index]
            normalized = normalize(demo.goal)
            if is_leak(demo.goal, goal) or normalized in seen:
                continue
            selected.append(demo)
            seen.add(normalized)
            if len(selected) >= k:
                break
        return selected


def _marked_history(lines: list[str]) -> list[str]:
    marked = []
    for line in lines:
        action, result = line.rsplit(" -> ", 1) if " -> " in line else (line, "ok")
        marked.append(f"[{result}] {action}")
    return marked


def render_demo(d: Demo) -> str:
    parts = [f'Goal: "{d.goal}"', d.obs_header, *d.obs_lines]
    if d.script_output:
        parts.append(f"Script result: {d.script_output[:300]}")
    if d.last_batch:
        parts.append("Last batch:")
        parts.extend(_marked_history(d.last_batch))
    parts.extend(("Reply:", *d.batch))
    return "\n".join(parts)


def render_block(demos: list[Demo]) -> str:
    if not demos:
        return ""
    return ("# Similar worked examples (input you got, then your whole reply)\n\n"
            + "\n\n".join(render_demo(demo) for demo in demos)
            + "\n\n# Your input\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="v2-tune")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    bank = load_bank(args.spec)
    Path(args.out).write_text("".join(json.dumps(asdict(demo), ensure_ascii=False) + "\n"
                                     for demo in bank))
