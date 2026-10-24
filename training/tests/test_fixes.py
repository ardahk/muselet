import json
import random

from muselet_train.catalog import skill_by_name
from muselet_train.contexts import constrain
from muselet_train.decontam import REPO, eval_utterances
from muselet_train.fixes import ungrounded
from muselet_train.relabel_v2 import V2_RX
from muselet_train.route_render import RouteContext


def test_external_evals_are_loaded():
    ext = [s for s, _ in eval_utterances() if s.startswith("external/")]
    n = sum(1 for ln in (REPO / "evals" / "external" / "utterances.jsonl").read_text().splitlines() if ln.strip())
    assert len(ext) == n


def test_v2_regex_matches_catalog_phrasings():
    for name in ("bluetooth", "lock_screen", "empty_trash"):
        for ex in skill_by_name(name).examples:
            assert V2_RX.search(ex), ex
    for t in ("lock my screen", "lock up the macbook", "clear out the trash bin", "empty my trash", "turn off blue tooth"):
        assert V2_RX.search(t), t
    assert not V2_RX.search("move this file to the trash")


def _row(skill, utt, target):
    return {"skill": skill, "utterance": utt, "target": target}


def test_ungrounded_args():
    assert ungrounded(_row("move_to_trash", "trash the old draft", 'path="old draft"')) == []
    assert ungrounded(_row("move_to_trash", "get rid of notes.txt", "path=notes.txt")) == []
    assert ungrounded(_row("move_to_trash", "trash that", 'path="~/Desktop/report.pdf"')) == ["path"]
    assert ungrounded(_row("compose_email", "Tanaka still hasn't seen the revised deck",
                           'to=Tanaka body="here\'s the revised deck"')) == ["body"]
    assert ungrounded(_row("new_folder", "make a folder called taxes twenty on the desktop",
                           'parent="the desktop" name="taxes 20"')) == []
    assert ungrounded(_row("create_event", "Could you put 'Movie tickets pickup' on Friday at 9?",
                           'title="Movie tickets pickup" start="Friday at 9"')) == []
    assert ungrounded(_row("set_volume", "volume all the way up", "level=100")) == []
    assert ungrounded(_row("send_message", "text Priya's phone", "missing=body")) == []


def test_constrained_contexts():
    rng = random.Random(0)
    base = RouteContext(app="Finder", focused='row "Downloads"', selection=False)
    assert constrain("copy_selection", base, rng).selection
    assert constrain("premiere_command", base, rng).app == "Premiere Pro"
    assert constrain("type_text", base, rng).focused.startswith(("textfield", "textarea"))
    assert constrain("open_app", base, rng) == base
    assert json.dumps(True)


def test_ask_rule_verdict():
    from muselet_train.ask_rule import verdict

    assert verdict(["level"], "missing=level", ["level"]) == "ask"
    assert verdict(["level"], "level=40", []) == "concrete"
    assert verdict(["to", "body"], 'to="Dana" missing=body', ["body"]) == "ask"
    assert verdict(["path"], 'path="~/Downloads" missing=path', ["path"]) == "concrete"
    assert verdict([], "", None) == "concrete"
    assert verdict(["to"], "", None) == "error"


def test_short_edit1_decontam():
    from muselet_train.decontam import Index

    idx = Index([("route_v1", "shoot him a text"), ("route_v1", "set the volume"), ("route_v1", "remind me")])
    assert idx.match("shoot her a text")[0] in ("short_edit1", "char5", "bigram")
    assert idx.match("set volume")
    assert idx.match("remind me later")
    assert idx.match("set the volume to forty percent please") is None
    assert idx.match("open the trash") is None
