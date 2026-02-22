# BlackBoard/src/models.py
# @ai-rules:
# 1. [Constraint]: All models are Pydantic BaseModel. Use Field() for defaults and descriptions.
# 2. [Pattern]: MessageStatus enum gates the read-receipt protocol (SENT -> DELIVERED -> EVALUATED).
# 3. [Gotcha]: ConversationTurn.status defaults to SENT for backward compat with existing Redis data.
# 4. [Pattern]: EventInput.evidence uses field_validator to coerce plain str -> EventEvidence for backward compat with existing Redis data.
# 5. [Pattern]: EventDocument.slack_* fields and ConversationTurn.source are Optional for backward compat with existing Redis data (pre-Slack events have None).
"""Pydantic schemas for Darwin Blackboard state layers."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Telemetry Protocol (matches DESIGN.md lines 94-107)
# =============================================================================

class Dependency(BaseModel):
    """A service dependency (edge in the topology graph)."""
    target: str = Field(..., description="Target service name")
    type: str = Field(..., description="Dependency type: db, http, cache, etc.")
    env_var: Optional[str] = Field(None, description="Environment variable name for this dependency")


class Metrics(BaseModel):
    """Runtime metrics for a service."""
    # Note: CPU can exceed 100% on multi-core systems or due to K8s metrics timing
    # Memory can briefly exceed 100% with swap. No upper bound enforced.
    cpu: float = Field(0.0, ge=0.0, description="CPU usage percentage")
    memory: float = Field(0.0, ge=0.0, description="Memory usage percentage")
    error_rate: float = Field(0.0, ge=0.0, description="Error rate percentage")


class Topology(BaseModel):
    """Service topology information."""
    dependencies: list[Dependency] = Field(default_factory=list)


class GitOpsMetadata(BaseModel):
    """
    GitOps coordinates for self-describing services.
    
    Allows SysAdmin to discover where to make changes for this service.
    """
    repo: Optional[str] = Field(None, description="GitHub repo (e.g., 'The-Darwin-Project/Store')")
    repo_url: Optional[str] = Field(None, description="Full clone URL (e.g., 'https://github.com/The-Darwin-Project/Store.git')")
    helm_path: Optional[str] = Field(None, description="Path to Helm values.yaml within repo")


class TelemetryPayload(BaseModel):
    """
    Telemetry payload from self-aware applications.
    
    Schema defined in DESIGN.md section 4.1.
    """
    service: str = Field(..., description="Service name (e.g., inventory-api)")
    version: str = Field("unknown", description="Service version (e.g., v2.0)")
    metrics: Metrics = Field(default_factory=Metrics)
    topology: Topology = Field(default_factory=Topology)
    gitops: Optional[GitOpsMetadata] = Field(default=None, description="GitOps coordinates for this service")
    pod_ips: list[str] = Field(default_factory=list, description="Pod IP addresses for IP-to-name correlation")


# =============================================================================
# Service State (Metadata Layer)
# =============================================================================

class Service(BaseModel):
    """A service in the Blackboard state."""
    name: str
    version: str = "unknown"
    metrics: Metrics = Field(default_factory=Metrics)
    dependencies: list[str] = Field(default_factory=list, description="List of dependency target names")
    last_seen: float = Field(default_factory=time.time, description="Unix timestamp of last telemetry")
    source_repo_url: Optional[str] = Field(None, description="Application source code repository URL")
    gitops_repo: Optional[str] = Field(None, description="GitOps repo short name (owner/repo)")
    gitops_repo_url: Optional[str] = Field(None, description="GitOps repository URL (Helm charts, values)")
    gitops_config_path: Optional[str] = Field(None, description="Config path within gitops repo (e.g., helm/values.yaml, kustomize/overlays)")
    replicas_ready: Optional[int] = Field(None, description="Number of ready replicas from K8s")
    replicas_desired: Optional[int] = Field(None, description="Desired replica count from K8s")


# =============================================================================
# Metrics History (Time-Series Layer)
# =============================================================================

class MetricPoint(BaseModel):
    """A single metric data point."""
    timestamp: float
    value: float


class MetricSeries(BaseModel):
    """Time-series data for a metric."""
    service: str
    metric: str  # cpu, memory, error_rate
    data: list[MetricPoint] = Field(default_factory=list)


# =============================================================================
# Graph Visualization (Cytoscape.js - GRAPH_SPEC.md)
# =============================================================================

class NodeType(str, Enum):
    """Types of nodes in the architecture graph."""
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    EXTERNAL = "external"


class HealthStatus(str, Enum):
    """Health status for nodes."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class GraphNode(BaseModel):
    """A node in the architecture graph."""
    id: str = Field(..., description="Unique node identifier (service name)")
    type: NodeType = Field(..., description="Node type determines shape/icon")
    label: str = Field(..., description="Display label")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional data: version, health, cpu, memory, replicas"
    )


class GraphEdge(BaseModel):
    """An edge in the architecture graph."""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    protocol: str = Field("HTTP", description="Wire protocol: HTTP, SQL, REDIS, gRPC, etc.")
    type: str = Field("hard", description="Dependency type: 'hard' or 'async'")


class TicketNode(BaseModel):
    """An ephemeral node representing an active event/ticket in the graph."""
    event_id: str
    status: str = Field(..., description="EventStatus value: new, active, deferred, waiting_approval")
    source: str = Field(..., description="aligner, chat, slack, headhunter (future)")
    reason: str = Field(..., description="Truncated event reason (first 80 chars)")
    turn_count: int
    elapsed_seconds: float
    current_agent: str | None = None
    defer_count: int = 0
    has_work_plan: bool = False
    resolved_service: str | None = None


class GraphResponse(BaseModel):
    """Response for /topology/graph endpoint."""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    tickets: list[TicketNode] = Field(default_factory=list, description="Active event tickets as ephemeral nodes")


# =============================================================================
# Architecture Events (for correlating metrics with changes)
# =============================================================================

class EventType(str, Enum):
    """Types of architecture events."""
    TELEMETRY_RECEIVED = "telemetry_received"
    SERVICE_DISCOVERED = "service_discovered"
    # Drift detection (version changes)
    DEPLOYMENT_DETECTED = "deployment_detected"
    # Anomaly events (Aligner observations)
    HIGH_CPU_DETECTED = "high_cpu_detected"
    HIGH_MEMORY_DETECTED = "high_memory_detected"
    HIGH_ERROR_RATE_DETECTED = "high_error_rate_detected"
    ANOMALY_RESOLVED = "anomaly_resolved"
    ALIGNER_OBSERVATION = "aligner_observation"  # Generic: Flash describes what it sees
    # Architect autonomous analysis
    ARCHITECT_ANALYZING = "architect_analyzing"
    # SysAdmin execution
    SYSADMIN_EXECUTING = "sysadmin_executing"


class ArchitectureEvent(BaseModel):
    """An architecture event for correlation with metrics."""
    type: EventType
    timestamp: float = Field(default_factory=time.time)
    details: dict[str, Any] = Field(default_factory=dict)
    narrative: Optional[str] = None  # Human-readable explanation of the event


# =============================================================================
# Snapshot (Context for Architect)
# =============================================================================

class TopologySnapshot(BaseModel):
    """Current topology state (for Mermaid generation)."""
    services: list[str] = Field(default_factory=list)
    edges: dict[str, list[str]] = Field(default_factory=dict, description="service -> [dependencies]")


class Snapshot(BaseModel):
    """
    Complete Blackboard snapshot for Architect context.
    
    Combines Structure + Metadata for AI reasoning.
    """
    topology: TopologySnapshot = Field(default_factory=TopologySnapshot)
    services: dict[str, Service] = Field(default_factory=dict, description="service_name -> Service")


# =============================================================================
# Chart Data (for Resources Consumption visualization)
# =============================================================================

class ChartData(BaseModel):
    """Aggregated data for resources consumption chart."""
    series: list[MetricSeries] = Field(default_factory=list)
    events: list[ArchitectureEvent] = Field(default_factory=list)


# =============================================================================
# Conversation History
# =============================================================================

class ConversationMessage(BaseModel):
    """A single message in a conversation."""
    role: Literal["user", "assistant"]
    content: str
    timestamp: float = Field(default_factory=time.time)


# =============================================================================
# Event Queue (Conversation Queue System)
# =============================================================================

class EventStatus(str, Enum):
    """Event lifecycle states."""
    NEW = "new"
    ACTIVE = "active"
    WAITING_APPROVAL = "waiting_approval"
    DEFERRED = "deferred"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EventMetrics(BaseModel):
    """Snapshot metrics attached to event evidence."""
    cpu: float = 0.0
    memory: float = 0.0
    error_rate: float = 0.0
    replicas: str = "unknown"


class EventEvidence(BaseModel):
    """Structured evidence for event ticket cards and multi-source rendering."""
    display_text: str = Field(..., description="Human-readable evidence string")
    source_type: str = Field("unknown", description="aligner | chat | headhunter | ...")
    domain: str = Field("complicated", description="Cynefin: clear|complicated|complex|chaotic")
    severity: str = Field("warning", description="info|warning|critical")
    metrics: Optional[EventMetrics] = None


class EventInput(BaseModel):
    """Input data that triggered an event."""
    reason: str = Field(..., description="What triggered this event")
    evidence: "str | EventEvidence" = Field(..., description="Logs, metrics, event details")
    timeDate: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp",
    )

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, v: Any) -> Any:
        """Accept plain strings (legacy) and wrap into EventEvidence for backward compat."""
        if isinstance(v, str):
            return EventEvidence(display_text=v, source_type="unknown")
        return v


class MessageStatus(str, Enum):
    """Message delivery status (read receipt protocol)."""
    SENT = "sent"
    DELIVERED = "delivered"
    EVALUATED = "evaluated"


class ConversationTurn(BaseModel):
    """A single turn in an event conversation."""
    turn: int = Field(..., description="Turn number in conversation")
    actor: str = Field(..., description="brain, architect, sysadmin, developer, aligner, user")
    action: str = Field(
        ...,
        description="triage, investigate, review, execute, plan, question, clarify, approve, confirm, close, request_approval, route, decide, verify",
    )
    thoughts: Optional[str] = None
    result: Optional[str] = None
    plan: Optional[str] = Field(None, description="Markdown format plan")
    selectedAgents: Optional[list[str]] = None
    taskForAgent: Optional[dict[str, Any]] = None
    requestingAgent: Optional[str] = None
    executed: Optional[bool] = None
    evidence: Optional[str] = None
    waitingFor: Optional[str] = None
    pendingApproval: Optional[bool] = None
    image: Optional[str] = Field(None, description="Base64 data URI of an attached image")
    status: "MessageStatus" = Field(default=MessageStatus.SENT, description="Message delivery status")
    source: Optional[str] = Field(None, description="Origin channel: 'dashboard' | 'slack' | None (legacy)")
    user_name: Optional[str] = Field(None, description="Display name for multi-user conversations (e.g., 'Albert O.')")
    timestamp: float = Field(default_factory=time.time)
    response_parts: Optional[list[dict]] = Field(None, description="Raw model response parts for multi-turn replay (thought_signature, functionCall)")


class EventDocument(BaseModel):
    """A complete event document with conversation history."""
    id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:8]}")
    source: Literal["aligner", "chat", "slack", "headhunter"]
    status: EventStatus = EventStatus.NEW
    service: str = Field(..., description="Target service name")
    event: EventInput
    conversation: list[ConversationTurn] = Field(default_factory=list)
    # Slack correlation fields (None for non-Slack events)
    slack_thread_ts: Optional[str] = Field(None, description="Slack thread timestamp (correlation key)")
    slack_channel_id: Optional[str] = Field(None, description="DM channel or public channel ID")
    slack_user_id: Optional[str] = Field(None, description="Slack user who initiated (for DM events)")


# =============================================================================
# API Response Models
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "brain_online"


class ChatRequest(BaseModel):
    """Chat request to Architect."""
    message: str = Field(..., description="User intent (e.g., 'Scale inventory-api to 3 replicas')")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for multi-turn context")


class ChatResponse(BaseModel):
    """Chat response from Architect."""
    message: str
    plan_id: Optional[str] = None
    conversation_id: Optional[str] = Field(None, description="Conversation ID for follow-up messages")
