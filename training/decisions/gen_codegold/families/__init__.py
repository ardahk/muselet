from . import cg_counting, cg_long_policy, cg_multi_hop, cg_numeric, cg_probability, cg_temporal, cg_trap

GENERATORS = {
    "cg_counting": cg_counting.generate,
    "cg_multi_hop": cg_multi_hop.generate,
    "cg_long_policy": cg_long_policy.generate,
    "cg_temporal": cg_temporal.generate,
    "cg_numeric": cg_numeric.generate,
    "cg_probability": cg_probability.generate,
    "cg_trap": cg_trap.generate,
}
