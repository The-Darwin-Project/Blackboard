# BlackBoard/src/state/ports.py
# @ai-rules:
# 1. [Constraint]: Protocols only — no implementation logic. BlackboardState satisfies via structural typing.
# 2. [Constraint]: No imports from src/agents/ — this module defines the state boundary.
# 3. [Pattern]: Each Protocol maps to one domain cluster in BlackboardState (Schedules, Observations, etc.).
# 4. [Pattern]: Model types in TYPE_CHECKING block — Protocols are the interface, models are the data.
# 5. [Gotcha]: BlackboardState methods that lack return type annotations need explicit types here.
"""Domain Port definitions for BlackboardState.

Each Protocol represents one bounded domain cluster. BlackboardState
implements all Protocols via structural typing (no inheritance needed).
Consumers receive the narrow Protocol they need — routes keep the
BlackboardState facade type.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing import List, Optional

    from ..models import (
        ArchitectureEvent,
        ChartData,
        ConversationMessage,
        ConversationTurn,
        EventDocument,
        EventEvidence,
        EventStatus,
        EventType,
        GraphResponse,
        MessageStatus,
        MetricPoint,
        ScheduledEvent,
        Service,
        Snapshot,
        TelemetryPayload,
        TopologySnapshot,
    )


@runtime_checkable
class ScheduleRepository(Protocol):
    """Port for TimeKeeper schedule persistence.

    10 methods, 2 consumers (routes/timekeeper.py, observers/timekeeper.py).
    Zero cross-domain dependencies — cleanest domain boundary.
    """

    async def create_schedule(self, sched: ScheduledEvent) -> str: ...

    async def get_schedule(self, sched_id: str) -> ScheduledEvent | None: ...

    async def list_schedules(self) -> list[ScheduledEvent]: ...

    async def update_schedule(self, sched_id: str, updates: dict) -> bool: ...

    async def delete_schedule(self, sched_id: str, created_by: str) -> bool: ...

    async def toggle_schedule(self, sched_id: str, enabled: bool) -> bool: ...

    async def count_user_schedules(self, email: str) -> int: ...

    async def pop_due_schedule(self) -> tuple[str, ScheduledEvent] | None: ...

    async def requeue_schedule(self, sched_id: str, score: float) -> None: ...

    async def advance_schedule(self, sched_id: str, next_fire_at: float) -> None: ...


@runtime_checkable
class ObservationRepository(Protocol):
    """Port for observations, ops journal, and field notes notebook.

    16 methods, 3 consumers (routes/observations.py, routes/journal.py, routes/notebook.py).
    Cross-domain: record_observation/list_observations internally call get_event()
    for phase/age derivation — resolved at BlackboardState facade level.
    """

    # --- Observations (numeric series) ---

    async def record_observation(
        self, event_id: str, name: str, value: float, unit: str, brain_phase: str = "",
    ) -> dict: ...

    async def list_observations(
        self,
        event_id: str | None = None,
        service: str | None = None,
        name: str | None = None,
    ) -> dict: ...

    async def get_observation_summary(self, event_id: str) -> Optional[dict]: ...

    # --- Ops Journal (per-service capped LIST) ---

    async def append_journal(self, service: str, entry: str) -> None: ...

    async def get_journal(self, service: str) -> list[str]: ...

    async def get_recent_journal_entries(
        self, limit: int = 30, per_service: int = 3,
    ) -> list[str]: ...

    # --- Field Notes Notebook (HASH) ---

    async def take_note(
        self, event_id: str, content: str, category: str,
    ) -> dict: ...

    async def get_notes(self) -> list[dict]: ...

    async def update_note(
        self, note_id: str, content: str | None = None, category: str | None = None,
    ) -> bool: ...

    async def delete_note(self, note_id: str) -> bool: ...

    async def drain_notes(self) -> list[dict]: ...

    async def has_drained_notes(self) -> bool: ...

    async def get_drained_notes(self) -> list[dict]: ...

    async def clear_drained_notes(self) -> None: ...

    async def quarantine_drained_notes(self) -> None: ...

    async def increment_digest_retries(self) -> int: ...


@runtime_checkable
class MetricsRepository(Protocol):
    """Port for metrics time-series, architecture events, and flow observability.

    Cross-domain: get_chart_data internally calls get_events_in_range
    (architecture event correlation). get_flow_metrics references Event Queue keys.
    """

    async def record_metric(
        self, service: str, metric: str, value: float, source: str = "self-reported",
    ) -> None: ...

    async def get_metric_history(
        self,
        service: str,
        metric: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        interpolate: bool = True,
    ) -> List[MetricPoint]: ...

    async def get_current_metrics(self, service: str) -> dict[str, float]: ...

    async def record_event(
        self, event_type: EventType, details: dict, narrative: Optional[str] = None,
    ) -> None: ...

    async def get_events_in_range(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 200,
    ) -> List[ArchitectureEvent]: ...

    async def get_events_for_service(
        self,
        service: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 200,
    ) -> List[ArchitectureEvent]: ...

    async def get_chart_data(
        self,
        services: List[str],
        metrics: Optional[List[str]] = None,
        range_seconds: int = 3600,
    ) -> ChartData: ...

    async def get_flow_metrics(self) -> dict: ...

    async def persist_flow_snapshot(self, snapshot: object) -> None: ...

    async def get_flow_history(
        self, range_seconds: int = 3600, downsample: bool = True,
    ) -> list: ...

    async def get_latest_flow_snapshot(self) -> object | None: ...


@runtime_checkable
class TopologyRepository(Protocol):
    """Port for service topology graph, service metadata, and discovery.

    18 methods, 8 consumers (K8s observer, aligner, routes/topology, routes/telemetry, etc.).
    Cross-domain: get_graph_data calls get_current_metrics (MetricsRepository).
    get_snapshot combines topology + service metadata.
    """

    async def add_service(self, name: str) -> None: ...

    async def remove_service(self, name: str) -> int: ...

    async def add_edge(self, source: str, target: str) -> None: ...

    async def add_edge_with_metadata(
        self,
        source: str,
        target: str,
        protocol: str = "",
        edge_type: str = "",
        env_var: str = "",
    ) -> None: ...

    async def get_edge_metadata(self, source: str, target: str) -> dict: ...

    async def get_services(self) -> list[str]: ...

    async def get_edges(self, service: str) -> list[str]: ...

    async def register_service_ips(self, service: str, ips: list[str]) -> None: ...

    async def resolve_ip_to_service(self, target: str) -> str: ...

    async def get_topology(self) -> TopologySnapshot: ...

    async def get_graph_data(self) -> GraphResponse: ...

    async def generate_mermaid(self) -> str: ...

    async def update_service_metadata(
        self,
        name: str,
        cpu: float = 0.0,
        memory: float = 0.0,
        error_rate: Optional[float] = None,
        version: Optional[str] = None,
        source_repo_url: Optional[str] = None,
        gitops_repo: Optional[str] = None,
        gitops_repo_url: Optional[str] = None,
        gitops_config_path: Optional[str] = None,
    ) -> None: ...

    async def update_service_discovery(
        self,
        name: str,
        version: str,
        source_repo_url: Optional[str] = None,
        gitops_repo: Optional[str] = None,
        gitops_repo_url: Optional[str] = None,
        gitops_config_path: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> None: ...

    async def update_service_replicas(
        self, name: str, ready: int, desired: int,
    ) -> None: ...

    async def get_service(self, name: str) -> Optional[Service]: ...

    async def get_all_services(self) -> dict[str, Service]: ...

    async def get_snapshot(self) -> Snapshot: ...

    async def get_escalation_flag(self, service: str) -> Optional[str]: ...

    async def set_escalation_flag(
        self, service: str, event_id: str, reason: str,
    ) -> None: ...

    async def clear_escalation_flag(
        self, service: str, expected_event_id: str | None = None,
    ) -> int: ...


@runtime_checkable
class EscalationRepository(Protocol):
    """Port for escalation staging, reports, and shift consolidation.

    Nightwatcher staging (darwin:nightwatcher:*), report persistence
    (darwin:report:*), and shift reports (darwin:nightwatcher:shift:*).
    Cross-domain: persist_report internally calls get_event, get_service,
    generate_mermaid, get_journal, get_observation_summary — resolved at
    BlackboardState facade level.
    """

    # --- Nightwatcher staging ---

    async def stage_escalation(self, data: object) -> None: ...

    async def lease_pending_escalations(
        self, before_ts: float,
    ) -> tuple[list, list[str]]: ...

    async def commit_inflight(self, json_members: list[str]) -> None: ...

    async def requeue_inflight(self) -> int: ...

    async def count_pending_escalations(self) -> int: ...

    async def restage_orphans(self, json_members: list[str]) -> int: ...

    # --- Report persistence (90-day TTL) ---

    async def persist_report(self, event_id: str) -> None: ...

    async def list_reports(
        self, limit: int = 50, offset: int = 0, service: Optional[str] = None,
    ) -> list[dict]: ...

    async def search_reports(
        self,
        *,
        limit: int = 50,
        cursor: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        service: Optional[str] = None,
        source: Optional[str] = None,
        domain: Optional[str] = None,
        severity: Optional[str] = None,
        q: Optional[str] = None,
    ) -> dict: ...

    async def get_report(self, event_id: str) -> Optional[dict]: ...

    # --- Shift reports ---

    async def persist_shift_report(self, report: object) -> None: ...

    async def get_shift_report(self, date: str, window: str) -> object | None: ...

    async def list_shift_reports(
        self, from_ts: float, to_ts: float,
    ) -> list[dict]: ...


@runtime_checkable
class CortexRepository(Protocol):
    """Port for JARVIS/Cortex UI surface: proposals, shadow interventions, handoff reports.

    5 methods, 1 consumer (routes/cognitive_graph.py).
    Zero cross-domain dependencies — all pure Redis primitives.
    """

    async def get_shadow_event_ids(self) -> list[str]: ...

    async def get_shadow_interventions(
        self, event_id: str, limit: int = 50,
    ) -> list[dict]: ...

    async def get_proposals(
        self, limit: int = 100, include_dismissed: bool = False,
    ) -> list[dict]: ...

    async def dismiss_proposals(self, timestamps: list) -> int: ...

    async def get_handoff_reports(self, limit: int = 100) -> list[dict]: ...


@runtime_checkable
class EventRepository(Protocol):
    """Port for the core event lifecycle: creation, conversation, queue, and closure.

    42 methods. The largest domain — all WATCH/MULTI operations on EventDocument stay here.
    Cross-domain: close_event interacts with Topology (get_service),
    Observations (cleanup), and Reports (persist_report) — resolved
    at BlackboardState facade level.
    """

    # --- Event CRUD ---

    async def create_event(
        self,
        source: str,
        service: str,
        reason: str,
        evidence: str | EventEvidence,
        subject_type: str = "service",
        created_by_email: Optional[str] = None,
        slack_channel_id: Optional[str] = None,
        slack_thread_ts: Optional[str] = None,
        slack_user_id: Optional[str] = None,
    ) -> str: ...

    async def get_event(self, event_id: str) -> Optional[EventDocument]: ...

    # --- Conversation turns (WATCH/MULTI) ---

    async def append_turn(self, event_id: str, turn: ConversationTurn) -> int: ...

    async def mark_turns_delivered(self, event_id: str, up_to_turn: int) -> int: ...

    async def mark_turns_evaluated(
        self, event_id: str, up_to_turn: Optional[int] = None,
    ) -> int: ...

    async def mark_turn_status(
        self, event_id: str, turn_number: int, status: MessageStatus,
    ) -> bool: ...

    async def update_turn_evidence(
        self, event_id: str, turn_num: int, evidence: str,
    ) -> bool: ...

    # --- Event lifecycle ---

    async def transition_event_status(
        self, event_id: str, from_status: str, to_status: EventStatus,
    ) -> bool: ...

    async def close_event(
        self, event_id: str, summary: str, close_reason: str = "resolved",
    ) -> None: ...

    async def stamp_event(self, event_id: str, **fields: object) -> None: ...

    # --- Event queue ---

    async def dequeue_event(self) -> Optional[str]: ...

    async def get_active_events(self) -> list[str]: ...

    async def get_active_events_with_status(self) -> dict[str, str]: ...

    async def find_active_event_by_source(self, source: str) -> str | None: ...

    # --- Approval parking ---

    async def park_for_approval(self, event_id: str) -> None: ...

    async def resume_from_approval(self, event_id: str) -> None: ...

    async def get_waiting_approval_events(self) -> list[str]: ...

    # --- Event metadata updates (WATCH/MULTI) ---

    async def update_event_domain(self, event_id: str, brain_domain: str) -> None: ...

    async def update_event_phase(self, event_id: str, brain_phase: str) -> None: ...

    async def update_event_gitlab_context(self, event_id: str, updates: dict) -> None: ...

    async def update_event_github_context(self, event_id: str, updates: dict) -> None: ...

    async def update_event_kargo_context(self, event_id: str, updates: dict) -> None: ...

    async def update_event_severity(self, event_id: str, brain_severity: str) -> None: ...

    async def update_event_sticky_notes(
        self, event_id: str, sticky_notes: list[dict], unread_notes: int,
    ) -> None: ...

    async def update_event_slack_context(
        self, event_id: str, channel_id: str, thread_ts: str, user_id: str = "",
    ) -> None: ...

    # --- Slack thread mapping ---

    async def get_event_by_slack_thread(
        self, channel_id: str, thread_ts: str,
    ) -> Optional[str]: ...

    async def delete_slack_mapping(self, channel_id: str, thread_ts: str) -> None: ...

    # --- Closed events ---

    async def get_closed_event_ids(self, limit: int = 500) -> list[str]: ...

    async def get_recent_closed_for_service(
        self, service: str, minutes: int = 15,
    ) -> list[tuple[str, float, str]]: ...

    async def get_recent_closed_by_source(
        self, source: str, minutes: int = 30,
    ) -> list[EventDocument]: ...

    # --- Deferred events ---

    async def defer_event_status(
        self, event_id: str, defer_until: float, delay: int,
    ) -> bool: ...

    # --- Closed event queries ---

    async def get_recently_closed_event_ids(
        self, limit: int = 50, since_seconds: int = 86400,
    ) -> list[str]: ...

    async def get_all_closed_event_ids(self) -> list[str]: ...

    # --- Jira mission state ---

    async def clear_jira_mission_state(self, issue_key: str) -> None: ...

    # --- Headhunter feedback ---

    async def is_feedback_sent(self, event_id: str) -> bool: ...

    async def mark_feedback_sent(self, event_id: str, ttl: int = 172800) -> None: ...

    # --- Defer timestamps ---

    async def resolve_defer_timestamps(
        self, event_id: str, event: EventDocument,
    ) -> tuple[float | None, float | None]: ...

    # --- Legacy conversation (separate from Event Queue) ---

    async def create_conversation(self) -> str: ...

    async def get_conversation(self, conversation_id: str) -> List[ConversationMessage]: ...

    async def append_to_conversation(
        self, conversation_id: str, message: ConversationMessage,
    ) -> None: ...
