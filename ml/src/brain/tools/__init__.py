"""Compatibility shim for legacy brain-tool callers. App/analysis skills
are router intents only — the AI operates the app's UI; there are no coded
task engines to import or execute here.
"""

import logging

log = logging.getLogger("brain.tools")


async def run(orch, name: str, args: dict, utterance: str) -> str:
    """Delegate to the agentic planner; never executes a tools.<name>
    module, even if one is importable."""
    trace = orch.tracer.current or {"decisions": []}
    return await orch._agentic_route(name, args, utterance, trace)
