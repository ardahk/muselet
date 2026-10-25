"""brain-52 (wip/local c156d18): first-turn planner 'ask' is rejected whenever the goal contains some/any/something..., including destructive/send goals where the ask is for a missing required fact."""
import pytest
from test_fallback_planner import FakePlanner, _run, _setup


@pytest.mark.parametrize("utterance,question", [
    ("delete some old files from my desktop", "Which files should I delete?"),
    ("send some photos to mom", "Which photos should I send?"),
])
def test_required_fact_ask_not_rejected(tmp_path, utterance, question):
    planner = FakePlanner([[f'ask "{question}"'], ['done "done"']])
    _, _, orch = _setup(tmp_path, {utterance.lower(): ("MULTI_STEP", 0.9)},
                        planner=planner)
    _run(orch.handle_utterance(utterance))
    assert planner.calls == 1, planner.calls
