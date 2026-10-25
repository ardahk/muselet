import pytest

from brain.finish import app_finish


@pytest.mark.parametrize("skill,args,want", [
    ("start_timer", {"duration": "10 minutes"},
     "Clock shows a running countdown of about 10 minutes"),
    ("start_timer", {"duration": 600},
     "Clock shows a running countdown of about 10 minutes"),
    ("start_timer", {"duration": 90},
     "Clock shows a running countdown of about 90 seconds"),
    ("start_timer", {},
     "Clock shows a running countdown"),
    ("create_event", {
        "title": "Dentist", "start": "2026-10-26T15:00:00"},
     "the event Dentist appears in Calendar on Monday Oct 26 at 3:00 PM"),
    ("create_event", {"title": "Trip", "start": "next week"},
     "the event Trip appears in Calendar on next week"),
    ("create_event", {"title": "Lunch"},
     "the event Lunch appears in Calendar"),
    ("create_reminder", {"title": "Call Sam"},
     "the reminder Call Sam appears in Reminders"),
    ("new_note", {"body": "buy oat milk and coffee beans"},
     "a new note containing buy oat milk and coffee beans is open"),
    ("compose_text", {"topic": "packing list", "title": "Travel"},
     "a new note containing packing list is open"),
    ("send_message", {"to": "Caleb"},
     "the message to Caleb is typed in Messages and you have asked to confirm sending"),
    ("compose_email", {},
     "a draft reply with the text is visible in the reply box (not sent)"),
    ("draft_email", {},
     "a draft reply with the text is visible in the reply box (not sent)"),
    ("play_music", {"query": "jazz"},
     "jazz is playing (a pause control is visible / player state is playing)"),
    ("todays_agenda", {},
     "today's events are read back from Calendar"),
])
def test_app_finish(skill, args, want):
    assert app_finish(skill, args) == want


def test_unknown_app_has_no_finish_criterion():
    assert app_finish("finance_review", {}) is None
