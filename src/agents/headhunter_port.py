# BlackBoard/src/agents/headhunter_port.py
# @ai-rules:
# 1. [Constraint]: stdlib + typing only (plus intra-package .headhunter_models). No I/O,
#    no Pydantic, no async runtime deps.
# 2. [Pattern]: Protocol-based port defining the platform adapter contract for VCS Phase A/B polling heads.
# 3. [Gotcha]: Brain-facing methods (refresh_state, poll_status, extract_state_key) and GitHub-specific
#    Phase C (Issues) / Phase D (Review-Response) are NOT part of this Protocol — they stay isolated
#    from Phase A/B error boundaries (headhunter.py @ai-rules #17).
# 4. [Pattern]: TYPE_CHECKING guard for EventDocument to avoid circular imports.
"""
VCS Platform Port — defines the contract between the Headhunter orchestrator and platform adapters.

The orchestrator (Headhunter.run loop) calls these methods during Phase A/B without knowing which
platform it's talking to. Platform-specific Brain tools (refresh_gitlab_context, poll_gitlab_mr_status),
GitHub Issues (Phase C), and Review-Response (Phase D) remain explicitly outside VcsPlatformPort's
Phase A/B contract to preserve error isolation (@ai-rules #17).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .headhunter_models import VcsContext, VcsWorkItem

if TYPE_CHECKING:
    from ..models import EventDocument


@runtime_checkable
class VcsPlatformPort(Protocol):
    """Contract for a VCS platform Phase A/B polling adapter.

    Implementors: GitLabPlatform, GitHubPlatform.

    The orchestrator calls these methods in sequence during each Phase A/B poll cycle:
        1. get_active_keys() — dedup check
        2. poll_work_items() — fetch actionable items
        3. fetch_context(item) — enrich with platform data
        4. load_triage_instruction() — system instruction for LLM
        5. create_platform_event(item, plan, context) — push to Brain queue
        6. post_feedback(event) — notify platform on event close
        7. close() — release adapter-owned HTTP clients on shutdown
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

    async def poll_work_items(self) -> Sequence[VcsWorkItem | dict[str, Any]]:
        """Fetch actionable work items from the platform."""
        ...

    async def fetch_context(
        self, work_item: VcsWorkItem | dict[str, Any],
    ) -> VcsContext | dict[str, Any] | None:
        """Enrich a work item with platform-specific context.

        Returns a VcsContext (or compatible mapping) consumed by the LLM analysis
        prompt, or None to skip the item without creating an event (e.g. unauthorized
        @mention or fail-closed notes fetch failure).
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
        work_item: VcsWorkItem | dict[str, Any],
        plan_text: str,
        context: VcsContext | dict[str, Any],
    ) -> str:
        """Create a Darwin event with platform-specific evidence.

        Returns the event_id. Must set the appropriate context field
        (gitlab_context or github_context) on the EventEvidence.
        """
        ...

    async def post_feedback(self, event: EventDocument | object) -> None:
        """Post resolution feedback to the platform (comment, mark done, etc.).

        Called when a headhunter event is closed. Platform-specific semantics:
        - GitLab: post MR comment + mark_as_done on todo
        - GitHub: post PR comment + label transition + SHA recording
        """
        ...

    async def close(self) -> None:
        """Release adapter-owned HTTP resources (never close borrowed shared singletons)."""
        ...
