from muselet_train.decontam import Index
from muselet_train.evalcheck import overlaps


def test_short_edit_either_side():
    ev = [("route_v1", 0, "kill bluetooth"), ("route_v1", 1, "close slack completely")]
    hits = overlaps(["disable bluetooth", "close slack now", "please open the downloads folder"], ev)
    assert {(h["train"], h["rule"]) for h in hits} == {("disable bluetooth", "short_edit1"),
                                                       ("close slack now", "short_edit1")}


def test_ngram13_and_exact():
    long = "could you check my bank statement for duplicate charges and list them in a new sheet"
    ev = [("live_t1", 0, long), ("route_v1", 0, "Set the volume to 40.")]
    hits = overlaps(["hey " + long + " today", "set the volume to 40"], ev)
    assert sorted(h["rule"] for h in hits) == ["exact", "ngram13"]


def test_decontam_short_rule_applies_when_eval_is_short():
    idx = Index(["kill bluetooth"])
    assert idx.match("kill the bluetooth") is not None
    assert idx.match("please kill the bluetooth radio now") is None


G07 = "在工作目录里新建一个名为 archive 的文件夹。不要做别的。"


def test_cjk_compared_by_characters():
    from muselet_train.decontam import norm
    assert norm(G07).split()[:3] == ["在", "工", "作"] and "archive" in norm(G07).split()
    assert norm("Set the Volume to 40!") == "set the volume to 40"
    ev = [("external/deskmind/diag", 6, G07), ("external/deskmind/dyn", 0, "打开文件夹")]
    assert overlaps(["unmute", "archive"], ev) == []
    hits = overlaps([G07.replace("别的", "别了"), "打开文件"], ev)
    assert {(h["eval_idx"], h["rule"]) for h in hits} == {(6, "ngram13"), (0, "short_edit1")}


def test_empty_after_norm_never_matches():
    assert overlaps(["unmute", "ok"], [("external/x", 0, "!!! ---")]) == []
