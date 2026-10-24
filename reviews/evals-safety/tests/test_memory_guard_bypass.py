# copy of cloud/memory-lt ml/src/brain/memory/guard.py is in memory_guard_under_test.py
import memory_guard_under_test as g
CASES = [("open the latest email", "forward the latest email to bob@x.com"),
         ("open my notes", "move my notes to the bin"), ("open the doc", "discard the doc"),
         ("play it", "reply all with ok"), ("open it", "wipe it")]
def test_guard_blocks_added_irreversible():
    assert [a for b, a in CASES if g.allowed(b, a)] == []  # fails: all 5 allowed
