from datetime import datetime
from types import SimpleNamespace

import pytest

from brain.catalog import Catalog, CatalogError
from brain.planner import Planner, catalog_desc


@pytest.fixture(scope="module")
def cat():
    return Catalog.load()   # repo skills/catalog.json via upward search


def test_loads(cat):
    assert len(cat.skills) >= 30
    assert cat.skills["set_volume"]["risk"] == "safe"
    assert cat.skills["send_message"]["risk"] == "confirm"
    assert cat.skills["quit_app"]["risk"] == "confirm_if_unsaved"
    names = {o["name"] for o in cat.special_options}
    assert {"MULTI_STEP", "ASK", "REFUSE", "ANSWER"} <= names


def test_skill_kinds(cat):
    app_skills = {
        "start_timer", "create_event", "create_reminder", "new_note",
        "compose_text", "play_music", "todays_agenda", "send_message",
        "compose_email", "draft_email", "premiere_command", "premiere_edit",
    }
    assert all(cat.kind(name) in {"system", "app", "analysis"}
               for name in cat.skills)
    assert cat.app_skills() == app_skills


def test_hidden_app_skills_leave_system_controls_visible(cat):
    desc = catalog_desc(cat, lambda _: "", hidden=cat.app_skills())
    for name in cat.app_skills():
        assert f"{name}(" not in desc
    for name in ("open_app", "type_text", "open_url"):
        assert f"{name}(" in desc

    engine = SimpleNamespace(
        model_path="fake", model=None, tokenizer=None, body=None,
        lm_head=None, rr=None)
    planner = Planner(
        "fake", cat, engine=engine, few_shot=None,
        hidden_skills=cat.app_skills())
    for name in cat.app_skills():
        assert f"{name}(" not in planner.system
    for name in ("open_app", "type_text", "open_url"):
        assert f"{name}(" in planner.system


def test_validate_ok(cat):
    out = cat.validate_args("set_volume", {"level": "30"})
    assert out == {"level": 30}
    out = cat.validate_args("dark_mode", {"on": "true"})
    assert out == {"on": True}
    out = cat.validate_args("window_layout", {"layout": "left"})
    assert out == {"layout": "left"}


def test_missing_required(cat):
    with pytest.raises(CatalogError, match="missing required"):
        cat.validate_args("set_volume", {})


def test_unknown_arg(cat):
    with pytest.raises(CatalogError, match="unknown arg"):
        cat.validate_args("set_volume", {"bogus": 1})


def test_unknown_skill(cat):
    with pytest.raises(CatalogError, match="unknown skill"):
        cat.validate_args("nonexistent", {})


def test_enum_validation(cat):
    with pytest.raises(CatalogError):
        cat.validate_args("window_layout", {"layout": "diagonal"})


def test_int_range(cat):
    with pytest.raises(CatalogError):
        cat.validate_args("set_volume", {"level": 200})
    with pytest.raises(CatalogError):
        cat.validate_args("change_volume", {"delta": "loud"})


def test_confirmed_passthrough(cat):
    out = cat.validate_args("send_message",
                            {"to": "mom", "body": "hi", "confirmed": True})
    assert out["confirmed"] is True


def test_datetime(cat):
    out = cat.validate_args("create_event",
                            {"title": "x", "start": "2026-10-24T10:00:00"})
    local = datetime.fromisoformat("2026-10-24T10:00:00").astimezone()
    assert out["start"] == local.isoformat(timespec="seconds")
    assert datetime.fromisoformat(out["start"]).tzinfo is not None
    out = cat.validate_args("create_event", {
        "title": "x", "start": "2026-10-24T10:00:00+02:00"})
    assert out["start"] == "2026-10-24T10:00:00+02:00"
    with pytest.raises(CatalogError):
        cat.validate_args("create_event", {"title": "x", "start": "whenever"})


@pytest.mark.parametrize("value,want", [
    ("600", 600), (600, 600), (600.5, 600),
    ("10 minutes", 600), ("5", 5),
])
def test_duration_coercion(cat, value, want):
    assert cat.validate_args("start_timer", {"duration": value}) == {
        "duration": want}


def test_duration_rejects_bool(cat):
    with pytest.raises(CatalogError):
        cat.validate_args("start_timer", {"duration": True})
