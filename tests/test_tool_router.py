# BlackBoard/tests/test_tool_router.py
# @ai-rules:
# 1. [Pattern]: CI guard for handler registry completeness. Catches missed registrations AND wrong-key regressions.
# 2. [Constraint]: EXPECTED_HANDLERS must be updated when handlers are added or removed.
"""CI guard for the HANDLER_REGISTRY completeness."""
from __future__ import annotations


EXPECTED_HANDLERS = {
    "ask_agent_for_state",
    "classify_event",
    "close_event",
    "comment_jira_issue",
    "consult_deep_memory",
    "create_plan",
    "defer_event",
    "fetch_jira_issue",
    "get_plan_progress",
    "hold_watch",
    "inspect_event",
    "list_observations",
    "lookup_journal",
    "lookup_service",
    "message_agent",
    "notify_gitlab_result",
    "notify_user_slack",
    "post_sticky_note",
    "re_trigger_aligner",
    "read_sticky_notes",
    "record_observation",
    "refresh_github_context",
    "refresh_gitlab_context",
    "refresh_kargo_context",
    "reply_to_agent",
    "report_incident",
    "request_user_approval",
    "search_open_incidents",
    "respond_to_jarvis",
    "review_notes",
    "select_agent",
    "set_phase",
    "take_note",
    "transition_jira_issue",
    "wait_for_agent",
    "wait_for_jarvis",
    "wait_for_user",
    "wait_for_verification",
}


def test_handler_registry_completeness():
    """Verify all expected handlers are registered and no extras exist."""
    import src.agents.brain  # noqa: F401 — triggers side-effect imports
    from src.agents.tool_router import HANDLER_REGISTRY

    registered = set(HANDLER_REGISTRY.keys())
    missing = EXPECTED_HANDLERS - registered
    extra = registered - EXPECTED_HANDLERS
    assert not missing, f"Missing handlers: {missing}"
    assert not extra, f"Unexpected handlers: {extra}"


def test_handler_registry_count():
    """Sanity check: exactly 36 handlers registered."""
    import src.agents.brain  # noqa: F401
    from src.agents.tool_router import HANDLER_REGISTRY

    assert len(HANDLER_REGISTRY) == 38, (
        f"Expected 38 handlers, got {len(HANDLER_REGISTRY)}: {sorted(HANDLER_REGISTRY.keys())}"
    )
