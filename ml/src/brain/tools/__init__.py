"""Registry for `executor: brain` skills (catalog v2: finance_review,
advisor_prep, ...). A brain-executor skill runs `brain.tools.<name>.run`
locally instead of going to HandsKit. Missing modules -> "fallback".

Settled interface (other agents write tool modules against this):
    async def run(orch, args: dict, utterance: str) -> str   # in each tool
Tools may use orch.server.rpc/say/ui/confirm and orch.engine (route/args);
all MLX calls go through the single MLX worker.
"""

import importlib
import logging

log = logging.getLogger("brain.tools")


async def run(orch, name: str, args: dict, utterance: str) -> str:
    """Dispatch a brain-executor skill. Outcome:
    ok|failed|awaiting_user|cancelled|fallback."""
    try:
        mod = importlib.import_module(f"brain.tools.{name}")
    except ImportError:
        log.info("brain-executor skill %s not implemented yet", name)
        return "fallback"
    return await mod.run(orch, args, utterance)
