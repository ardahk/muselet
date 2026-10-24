"""Pass-16 fresh repros against main 2920225. Run from a main checkout:
PYTHONPATH=ml/src:ml/tests pytest reviews/brain/tests/test_brain_pass16.py
Every test here FAILS on 2920225 (each one demonstrates an open finding)."""
import types

from brain import protocol
from brain.orchestrator import abs_level, split_clauses
from brain.planner import BatchCutter
from test_orchestrator import FakeHands
from test_planner_loop import FakePlanner, _mk, _obs_elements, _up, run, trace_for


def test_brain16_relative_volume_not_absolute():
    assert abs_level("turn it up two to three notches") is None
    assert abs_level("turn the volume down a bit at 3 pm") is None
    assert abs_level("turn up the volume so I can listen to 2 songs") is None


def test_brain17_no_compound_split_for_one_phrase():
    # split -> two serial route passes before the normal path on every 'and'
    assert split_clauses("search for salt and pepper")[0] == ["search for salt and pepper"]


def test_brain18_batchcutter_counts_bare_catalog_skills():
    bc = BatchCutter()
    for ln in ["mute", "wifi on", "bluetooth off", "mute", "wifi off", "press #4"]:
        bc.push(ln)
    assert bc.done or bc.full, f"6 executed actions, cutter counted {bc.n}"


def test_brain14_confirm_not_carried_over_harmless_action():
    hands = FakeHands()
    hands.confirm_yes = True
    orig = FakeHands.reply

    async def reply(self, msg):
        if msg["method"] == "observe":
            return protocol.rpc_result(msg["id"], True, _obs_elements(
                [{"ref": 1, "role": "button", "label": "Send", "enabled": True, "frame": [0, 0, 10, 10]},
                 {"ref": 2, "role": "button", "label": "Settings", "enabled": True, "frame": [20, 0, 10, 10]}],
                app="Messages"))
        return await orig(self, msg)
    hands.reply = types.MethodType(reply, hands)
    planner = FakePlanner([['confirm "Open settings?"', "press #2", "press #1"], ['done "ok"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9961
        await _up(server, hands, orch, 9961)
        await orch._planner_loop("open settings", trace_for(orch))
        await hands.close(); await server.close()
    run(go())
    confirms = [m for m in hands.messages if m.get("t") == "confirm"]
    assert len(confirms) >= 2, "press Send ran on the confirm given for 'Open settings?'"


def test_brain12_unrelated_utterance_not_consumed_as_answer():
    hands = FakeHands()
    planner = FakePlanner([['ask "which folder?"'], ['done "ok"']])
    server, orch = _mk(0, planner, hands)

    async def go():
        server.port = 9962
        await _up(server, hands, orch, 9962)
        await orch._planner_loop("move it", trace_for(orch))
        await orch.handle_utterance("set the volume to thirty percent")
        await hands.close(); await server.close()
    run(go())
    assert not any('User answer: "set the volume' in (m["goal"] or "") for m in planner.user_msgs), \
        "a new command was fed to the old planner task as its answer"


def test_brain8_last_action_matches_training_format():
    raw = {"query": "weather"}       # orchestrator.py:423-425 formatting, verbatim
    parts = " ".join(f'{k}="{v}"' if isinstance(v, str) and " " in v else f"{k}={v}" for k, v in raw.items())
    assert parts == 'query="weather"'   # training contexts.py LAST_ACTIONS: web_search query="weather"
