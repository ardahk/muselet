import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals"))

import planner_offline
from brain.plan_bank import (
    BM25,
    Demo,
    PlanBank,
    _filter_demos,
    denylist,
    is_leak,
    load_bank,
    load_jsonl,
    normalize,
    render_block,
    render_demo,
    tokenize,
)


def _demo(goal, *, id=None, app="Finder", obs_header="app: Finder | window: \"Desktop\"",
          batch=None, category="single_step"):
    return Demo(goal=goal, app=app, category=category, obs_header=obs_header,
                batch=batch or ["press #1"], id=id)


def test_default_bank_is_all_v2_tune_rows_and_keeps_referenced_elements():
    rows = [json.loads(line) for line in (ROOT / "evals" / "planner_scenarios_v2.jsonl")
            .read_text().splitlines()]
    tune = [row for row in rows if row["split"] == "v2-tune"]
    demos = load_bank("v2-tune")
    ids, goals = denylist()
    print(f"v2-tune bank dropped: {load_bank.last_dropped}")
    dropped = load_bank.last_dropped
    assert dropped["total"] == dropped["id"] + dropped["goal"] + dropped["leak"]
    assert len(demos) == len(tune) - dropped["total"] and len(tune) == 130
    tune_ids = {row["id"] for row in tune}
    assert {demo.id for demo in demos} <= tune_ids
    assert tune_ids - {demo.id for demo in demos} == {"v2-mail-no-account"}
    assert dropped == {"total": 1, "id": 0, "goal": 0, "leak": 1}
    assert all(demo.id not in ids and normalize(demo.goal) not in set(goals) and
               not any(is_leak(demo.goal, goal) for goal in goals) for demo in demos)
    for demo in demos:
        source = next(row for row in tune if row["id"] == demo.id)
        assert demo.batch == source["gold"][0]
        assert len(demo.obs_lines) <= 12
        observation = source["observation"].splitlines()
        available = {ref for line in observation if (match := re.match(r"^#(\d+)\b", line))
                     for ref in [match.group(1)]}
        refs = set(re.findall(r"#(\d+)", "\n".join(demo.batch + (source.get("last_batch") or []))))
        focused = re.search(r"\bfocused:\s*#(\d+)", demo.obs_header)
        if focused:
            refs.add(focused.group(1))
        retained = {match.group(1) for line in demo.obs_lines
                    if (match := re.match(r"^#(\d+)\b", line))}
        assert refs & available <= retained


def test_jsonl_round_trip_and_missing_required_field(tmp_path):
    original = _demo("open a unique notebook")
    path = tmp_path / "bank.jsonl"
    path.write_text(json.dumps(asdict(original)) + "\n")
    assert load_jsonl(path) == [original]
    path.write_text('{"goal":"missing fields"}\n')
    with pytest.raises(ValueError, match="line 1.*app.*category"):
        load_jsonl(path)


def test_hf_loader_downloads_then_applies_denylist(monkeypatch, tmp_path):
    import huggingface_hub

    path = tmp_path / "bank.jsonl"
    path.write_text(json.dumps(asdict(_demo("a clean unique task", id="hf-clean"))) + "\n"
                    + json.dumps(asdict(_demo("turn wifi on", id="hf-leak"))) + "\n")
    seen = {}

    def download(**kwargs):
        seen.update(kwargs)
        return str(path)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    bank = load_bank("hf:org/repo:custom.jsonl")
    assert [demo.id for demo in bank] == ["hf-clean"]
    assert seen == {"repo_id": "org/repo", "filename": "custom.jsonl", "repo_type": "dataset"}
    assert load_bank.last_dropped["total"] == 1


def test_denylist_covers_every_frozen_source_and_filters_synthetic_demos():
    ids, goals = denylist()
    v1 = planner_offline.TUNE + planner_offline.HOLDOUT + planner_offline.HOLDOUT2
    v2_holdout = [json.loads(line) for line in
                  (ROOT / "evals" / "planner_scenarios_v2.jsonl").read_text().splitlines()
                  if json.loads(line)["split"] == "v2-holdout"]
    live = [json.loads(line) for line in (ROOT / "evals" / "live_t1.jsonl").read_text().splitlines()]
    external = [json.loads(line) for line in
                (ROOT / "evals" / "external" / "utterances.jsonl").read_text().splitlines()]
    assert len({row["id"] for row in v1}) >= 51
    assert len(v2_holdout) == 130
    assert len(live) >= 40 and len(external) >= 500
    assert ids and goals

    v1_holdout = next(row for row in planner_offline.HOLDOUT if row["goal"])
    live_row = live[0]
    hobby = next(row for row in external if row["source"].startswith("hobby"))
    desk = next(row for row in external if row["source"].startswith("deskmind"))
    goal = v1_holdout["goal"]
    variant = goal[:-1] + ("x" if goal[-1] != "x" else "y")
    clean = _demo("zorb noodle activate quasar ledger", id="clean")
    demos = [
        _demo(v2_holdout[0]["goal"], id="holdout-goal"),
        _demo("unique phrase for v1 id", id=v1_holdout["id"]),
        _demo(live_row["utterance"], id="live-goal"),
        _demo(hobby["text"], id="hobby-goal"),
        _demo(desk["text"], id="desk-goal"),
        _demo(variant, id="edit-distance"),
        clean,
    ]
    kept, dropped = _filter_demos(demos)
    assert kept == [clean]
    assert dropped["total"] == 6


def test_bm25_matching_idf_length_normalization_and_order():
    docs = [["alpha", "rare"], ["alpha", "common"], ["common", "other"]]
    bm25 = BM25(docs)
    assert bm25.scores(["rare"])[0] > bm25.scores(["common"])[1]
    assert bm25.scores(["alpha"])[0] > bm25.scores(["alpha"])[2]

    short = BM25([["needle"], ["needle", "pad", "pad", "pad"]], b=1)
    no_length_norm = BM25([["needle"], ["needle", "pad", "pad", "pad"]], b=0)
    assert short.scores(["needle"])[0] > short.scores(["needle"])[1]
    assert no_length_norm.scores(["needle"])[0] == no_length_norm.scores(["needle"])[1]

    demos = [_demo("alpha task"), _demo("alpha work"),
             _demo("beta task", app="Mail", obs_header='app: Mail | window: "Inbox"')]
    ranked = PlanBank(demos).retrieve("alpha mission", "app: Unknown | window: desktop", 1)
    assert ranked == [demos[0]]
    assert PlanBank([_demo("unrelated")]).retrieve(
        "zzq unmatchable", "app: NoApp | window: none", 2) == []
    assert PlanBank(demos).retrieve("query", "app: Finder | window: none", 0) == []


@pytest.mark.parametrize("a,b", [
    ("turn wifi on", "turn wifi on"),
    ("turn wifi on", "turn wifi xn"),
    ("turn wifi on", "turn wif on"),
    ("turn wifi on", "turn wifi on!"),
])
def test_is_leak_one_edit(a, b):
    assert is_leak(a, b)


def test_is_leak_two_edits_and_word_ngram_threshold():
    assert not is_leak("turn wifi on", "turn data on")
    words = "one two three four five six seven eight nine ten eleven twelve thirteen"
    assert is_leak(f"please {words} today", f"kindly {words} now")
    twelve = "one two three four five six seven eight nine ten eleven twelve"
    assert not is_leak(f"please {twelve} today", f"kindly {twelve} now")


def test_retrieve_excludes_self_near_duplicate_and_same_goal_duplicates():
    query = "create a folder in downloads named invoices"
    demos = [_demo(query), _demo("create a folder in downloads named invoicez"),
             _demo("make a new folder in downloads called invoices")]
    result = PlanBank(demos).retrieve(query, "app: Finder | window: Downloads", 2)
    assert demos[0] not in result and demos[1] not in result
    duplicate = _demo("open a different unique task")
    result = PlanBank([duplicate, _demo("open a different unique task")]).retrieve(
        "open a different unique task sometime", "app: Unknown | window: Desktop", 2)
    assert result == [duplicate]


def test_render_demo_exact_fewshot_layout():
    demo = Demo(
        goal="save this as final",
        app="Pages",
        category="recovery",
        obs_header='app: Pages | window: "Report.pages"',
        obs_lines=['#4 button "Save"'],
        batch=["press #4", 'expect appears "Saved"'],
        last_batch=["press #3 -> failed: stale_ref"],
        script_output="could not find earlier path",
    )
    assert render_demo(demo) == (
        'Goal: "save this as final"\n'
        'app: Pages | window: "Report.pages"\n'
        '#4 button "Save"\n'
        'Script result: could not find earlier path\n'
        'Last batch:\n'
        '[failed: stale_ref] press #3\n'
        'Reply:\n'
        'press #4\n'
        'expect appears "Saved"'
    )
    assert render_block([]) == ""
    assert render_block([demo]).startswith(
        "# Similar worked examples (input you got, then your whole reply)\n\n")
    assert render_block([demo]).endswith("\n\n# Your input\n")


def test_normalize_and_tokenize():
    assert normalize("  SET Wi-Fi, NOW! ") == "set wi fi now"
    assert tokenize("app Window #123 My Finder 42") == ["finder"]
