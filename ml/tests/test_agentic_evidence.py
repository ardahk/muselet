import pytest

from brain.finish import cart_count, evidence, progress_kind


@pytest.mark.parametrize(
    "kind,subject,obs,kwargs,positive",
    [
        (
            "timer_start", "", {
                "text": 'app: Clock | window: "Timers"\n'
                        '#1 button "Pause"\n#2 text "9:58 remaining"',
            }, {"args": {"duration": "10 minutes"}}, True,
        ),
        (
            "timer_start", "", {
                "text": 'app: Clock | window: "Timers"\n'
                        '#1 button "Pause"\n#2 text "4:59 remaining"',
            }, {"args": {"duration": "10 minutes"}}, False,
        ),
        (
            "timer", "", 'app: Clock | window: "Timers"\n#1 button "Resume"',
            {"goal": "pause the timer"}, True,
        ),
        (
            "timer", "", 'app: Clock | window: "Timers"\n#1 button "Pause"',
            {"goal": "pause the timer"}, False,
        ),
        (
            "reminder", "Call Sam", {
                "text": 'app: Reminders | window: "Today"\n'
                        '#4 row "Call Sam" value="Call Sam"',
            }, {}, True,
        ),
        (
            "reminder", "Call Sam", {
                "text": 'app: Reminders | window: "Today"\n'
                        '#4 textfield "Search" value="Call Sam"',
            }, {}, False,
        ),
        (
            "reminder", "Call Sam", {
                "text": 'app: Notes | window: "Untitled"\n'
                        '#4 row "Call Sam"',
            }, {}, False,
        ),
        (
            "note", "oat milk coffee beans", {
                "focused_ref": 2,
                "text": 'app: Notes | window: "Groceries" | focused: #2\n'
                        '#2 textarea "Note body" '
                        'value="Buy oat milk and coffee beans"',
            }, {}, True,
        ),
        (
            "note", "oat milk coffee beans", {
                "focused_ref": 2,
                "text": 'app: Notes | window: "Groceries" | focused: #2\n'
                        '#2 textarea "Note body" value="Buy oat milk"',
            }, {}, False,
        ),
        (
            "event", "Dentist", {
                "text": 'app: Calendar | window: "Week"\n'
                        '#8 cell "Dentist"',
            }, {}, True,
        ),
        (
            "event", "Dentist", {
                "text": 'app: Calendar | window: "Week"\n'
                        '#8 cell "Lunch"',
            }, {}, False,
        ),
        (
            "message", "hi there caleb", {
                "focused_ref": 2,
                "text": 'app: Messages | window: "New Message" | focused: #2\n'
                        '#2 textfield "Message" value="hi there caleb"',
            }, {"confirmed": True}, True,
        ),
        (
            "message", "hi there caleb", {
                "focused_ref": 2,
                "text": 'app: Messages | window: "New Message" | focused: #2\n'
                        '#2 textfield "Message" value="hi there caleb"',
            }, {"confirmed": False}, False,
        ),
        (
            "email", "quarterly schedule update", {
                "focused_ref": 7,
                "text": 'app: Mail | window: "Reply" | focused: #7\n'
                        '#7 textview "Reply" '
                        'value="Here is the quarterly schedule update"',
            }, {}, True,
        ),
        (
            "email", "quarterly schedule update", {
                "focused_ref": 7,
                "text": 'app: Mail | window: "Reply" | focused: #7\n'
                        '#7 textview "Reply" value=""',
            }, {}, False,
        ),
        (
            "directions", "", {
                "text": 'app: Maps | window: "Route"\n'
                        '#1 button "Directions"\n#9 text "18 min (5.2 mi)"',
            }, {}, True,
        ),
        (
            "directions", "", {
                "text": 'app: Maps | window: "Route"\n'
                        '#1 button "Directions"',
            }, {}, False,
        ),
        (
            "play", "", {
                "text": 'app: Music | window: "Now Playing"\n'
                        '#1 button "Pause"',
            }, {}, True,
        ),
        (
            "play", "", {
                "text": 'app: Music | window: "Now Playing"\n'
                        '#1 button "Play"',
            }, {}, False,
        ),
        (
            "cart", "", {"text": '#1 text "1 item in cart"'},
            {"baseline": 0}, True,
        ),
        (
            "cart", "", {"text": '#1 text "0 items in cart"'},
            {"baseline": 0}, False,
        ),
    ],
)
def test_progress_evidence(kind, subject, obs, kwargs, positive):
    assert evidence(kind, subject, obs=obs, progress=True, **kwargs) is positive


@pytest.mark.parametrize("skill,args,expected", [
    ("start_timer", {"duration": "10 minutes"}, ("timer_start", "",)),
    ("create_reminder", {"title": "Call Sam"}, ("reminder", "Call Sam")),
    ("new_note", {"title": "Shopping", "body": "oat milk"},
     ("note", "Shopping")),
    ("compose_text", {"topic": "packing list"}, ("note", "packing list")),
    ("create_event", {"title": "Dentist"}, ("event", "Dentist")),
    ("send_message", {"body": "hi there"}, ("message", "hi there")),
    ("compose_email", {"body": "weekly update"}, ("email", "weekly update")),
    ("draft_email", {"about": "the schedule"}, ("email", "the schedule")),
    ("play_music", {"query": "jazz"}, ("play", "jazz")),
])
def test_progress_kind_for_agentic_skills(skill, args, expected):
    kind, subject, got_args = progress_kind(
        "task\nUser answer: ignored", {"skill": skill, "args": args})
    assert (kind, subject) == expected
    assert got_args == args


@pytest.mark.parametrize("goal,expected", [
    ("pause the timer", ("timer", "", {})),
    ("add coffee to the cart", ("cart", "", {})),
    ("get directions to the library", ("directions", "the library", {})),
    ("do something generic", None),
])
def test_progress_kind_for_non_agentic_goals(goal, expected):
    assert progress_kind(goal) == expected


def test_progress_evidence_accepts_string_observation():
    assert evidence(
        "timer", obs='app: Clock\n#1 button "Resume"', goal="pause timer",
        progress=True)


def test_non_progress_unknown_evidence_remains_true():
    assert evidence("unknown")


def test_progress_unknown_evidence_is_false():
    assert not evidence("unknown", progress=True)


def test_cart_count_returns_latest_observation():
    assert cart_count(
        "2 items in cart\n~ #4 text 3 items in cart") == 3
