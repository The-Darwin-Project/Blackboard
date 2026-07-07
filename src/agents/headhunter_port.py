# BlackBoard/src/agents/headhunter_port.py
# @ai-rules:
# 1. [Constraint]: stdlib + typing only. No I/O, no Pydantic, no async runtime deps.
# 2. [Pattern]: Protocol-based port defining the platform adapter contract for VCS polling heads.
# 3. [Gotcha]: Brain-facing methods (refresh_state, poll_status, extract_state_key) are NOT
#    part of this Protocol — they're platform-specific and accessed via Headhunter delegate
#    methods. This Protocol covers only what the orchestrator loop needs.
# 4. [Pattern]: TYPE_CHECKING guard for EventDocument to avoid circular imports.
"""
VCS Platform Port — defines the contract between the Headhunter orchestrator and platform adapters.

The orchestrator (Headhunter.run loop) calls these methods without knowing which platform
it's talking to. Platform-specific Brain tools (refresh_gitlab_context, poll_gitlab_mr_status)
remain as direct methods on the adapter, accessed via delegation on the Headhunter instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState


@runtime_checkable
class VcsPlatformPort(Protocol):
    """Contract for a VCS platform polling adapter.

    Implementors: GitLabPlatform, GitHubPlatform (future).

    The orchestrator calls these methods in sequence during each poll cycle:
        1. get_active_keys() — dedup check
        2. poll_work_items() — fetch actionable items
        3. fetch_context(item) — enrich with platform data
        4. load_triage_instruction() — system instruction for LLM
        5. create_platform_event(item, plan, domain, context) — push to Brain queue
        6. post_feedback(event) — notify platform on event close

    classify_severity() is called during event creation to map platform
    signals to Darwin severity levels.
    """

    @property
    def platform_name(self) -> str:
        """Short identifier: 'gitlab', 'github'."""
        ...

    def enabled(self) -> bool:
        """Whether this platform adapter is configured and ready to poll."""
        ...

    async def get_active_keys(self) -> set:
        """Return dedup keys for currently active events on this platform.

        Keys are opaque tuples — the orchestrator uses them only for
        set membership checks, not for inspection.
        """
        ...

    async def poll_work_items(self) -> list[dict]:
        """Fetch actionable work items from the platform.

        Returns a list of normalized dicts. Each dict must contain at minimum:
            - A dedup key extractable by the adapter
            - Enough data for fetch_context() to enrich

        The orchestrator does NOT inspect these dicts — they're passed back
        to fetch_context() and create_platform_event() opaquely.
        """
        ...

    async def fetch_context(self, work_item: dict) -> dict:
        """Enrich a work item with platform-specific context.

        Returns a context dict consumed by the LLM analysis prompt.
        Must include fields the prompt builder expects (action_name,
        mr_title/pr_title, pipeline_status/check_status, etc.).
        """
        ...

    def load_triage_instruction(self) -> str:
        """Load the system instruction for LLM triage of this platform's work items."""
        ...

    def classify_severity(self, action: str, status: str) -> str:
        """Map platform action + CI status to Darwin severity (info/warning/critical)."""
        ...

    async def create_platform_event(
        self,
        work_item: dict,
        plan_text: str,
        domain: str,
        context: dict,
    ) -> str:
        """Create a Darwin event with platform-specific evidence.

        Returns the event_id. Must set the appropriate context field
        (gitlab_context or github_context) on the EventEvidence.
        """
        ...

    async def post_feedback(self, event: object) -> None:
        """Post resolution feedback to the platform (comment, mark done, etc.).

        Called when a headhunter event is closed. Platform-specific semantics:
        - GitLab: post MR comment + mark_as_done on todo
        - GitHub: post PR comment + mark notification as read
        """
        ...
