"""brain pass 26 repro (cloud/grounder-wire afb12a6): grounded clicks only check the planner's own description."""
import asyncio

from test_grounder_wire import _orch


def test_brain27_grounded_click_on_send_needs_confirm(tmp_path):
    """`press #ref` checks the real AX label against _DANGEROUS_LABEL; `click "<target>"` checks only the
    planner-written description (orchestrator.py _click_target). A pixel target described without the word
    (the Messages send arrow, a Mail paper-plane icon) is clicked with no confirm."""
    o, srv, _ = _orch(tmp_path)
    srv.confirm_yes = False
    r = asyncio.run(o._exec_action({"op": "click", "target": "the paper plane icon next to the message",
                                    "right": False, "double": False}))
    assert srv.confirms or not srv.acts(), \
        f"grounded click executed with no confirm and no check of what is under the point: {srv.acts()}"
