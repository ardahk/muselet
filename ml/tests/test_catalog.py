from datetime import datetime

import pytest

from brain.catalog import Catalog, CatalogError


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


def test_catalog_url_coercion():
    cat = Catalog({"skills": [{
        "name": "go", "args": [{"name": "url", "type": "url",
                                  "required": True}]
    }]})
    assert cat.validate_args("go", {"url": "gmail"})["url"] == \
        "https://mail.google.com"
