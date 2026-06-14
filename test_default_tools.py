from src.agents.tool_gates import evaluate_gates, GateContext
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

ctx = GateContext(
    brain_phase="dispatch",
    event_source="aligner",
    has_kargo_context=True,
    refresh_count=0,
    refresh_budget=10,
    agent_completions=0,
    unread_notes=0,
    is_defer_wake=False,
    conversation=[],
    context_flags={"brain_has_classified": True, "event_domain": "complicated"},
    iteration=1,
)

active = evaluate_gates(BRAIN_TOOL_SCHEMAS, ctx)
print([t["name"] for t in active])
