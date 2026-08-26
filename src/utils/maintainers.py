# BlackBoard/src/utils/maintainers.py
# @ai-rules:
# 1. [Constraint]: No project imports here -- must be importable from both src/agents/brain.py
#    and src/agents/handlers_integration.py (which itself forbids importing Brain).
# 2. [Pattern]: Single source of truth for maintainer-email resolution, used by the LLM
#    system-prompt template vars, the notify_user_slack tool-schema enum, and the Slack
#    fallback resolver -- so all three pick the same maintainer list for a given event.
"""Shared maintainer-resolution helpers for escalation routing.

Precedence: evidence.gitlab_context.maintainer.emails, then github_context, then
ci_context, then the subject_type-appropriate static env var
(JENKINS_OBSERVER_MAINTAINERS for ci_gating events, HEADHUNTER_MAINTAINERS otherwise),
then event.slack_user_id.
"""
from __future__ import annotations

import os

_CONTEXT_ATTRS = ("gitlab_context", "github_context", "ci_context")


def maintainer_env_key(subject_type: str | None) -> str:
    """Env var name holding the static maintainer email CSV for this subject_type."""
    return "JENKINS_OBSERVER_MAINTAINERS" if subject_type == "ci_gating" else "HEADHUNTER_MAINTAINERS"


def resolve_maintainer_emails(event) -> list[str]:
    """Extract a deduplicated list of maintainer emails from event evidence + static config."""
    emails: list[str] = []
    evidence = getattr(getattr(event, "event", None), "evidence", None)
    if evidence:
        for attr in _CONTEXT_ATTRS:
            if emails:
                break
            ctx = getattr(evidence, attr, None) or {}
            if isinstance(ctx, dict):
                emails.extend(ctx.get("maintainer", {}).get("emails", []))
    if not emails:
        subject_type = getattr(event, "subject_type", None)
        static = os.getenv(maintainer_env_key(subject_type), "")
        emails = [e.strip() for e in static.split(",") if e.strip()]
    if event and getattr(event, "slack_user_id", None):
        emails.append(event.slack_user_id)
    seen: set[str] = set()
    return [e for e in emails if e and e not in seen and not seen.add(e)]
