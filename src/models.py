# BlackBoard/src/models.py
"""Pydantic schemas for Darwin Blackboard state layers."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


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
    gitops_repo: Optional[str] = Field(None, description="GitHub repo for this service")
    gitops_repo_url: Optional[str] = Field(None, description="Full clone URL for this service")
    gitops_helm_path: Optional[str] = Field(None, description="Helm values path within repo")


# =============================================================================
# Plan Layer
# =============================================================================

class PlanStatus(str, Enum):
    """Plan lifecycle states."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanAction(str, Enum):
    """Supported plan actions (from Architect tools)."""
    SCALE = "scale"
    ROLLBACK = "rollback"
    RECONFIG = "reconfig"
    FAILOVER = "failover"
    OPTIMIZE = "optimize"


class Plan(BaseModel):
    """
    An infrastructure modification plan created by the Architect.
    
    Plans live forever in the Blackboard (no TTL).
    """
    id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    action: PlanAction
    service: str = Field(..., description="Target service name from topology")
    params: dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    reason: str = Field(..., description="Justification based on metrics/topology")
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = Field(default_factory=time.time)
    approved_at: Optional[float] = None
    executed_at: Optional[float] = None
    result: Optional[str] = Field(None, description="Execution result or error message")


class PlanCreate(BaseModel):
    """Schema for creating a new plan (from Architect function call)."""
    action: PlanAction
    service: str
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str


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


class GhostNode(BaseModel):
    """A ghost node representing a pending plan."""
    plan_id: str = Field(..., description="Associated plan ID")
    target_node: str = Field(..., description="Target service this plan affects")
    action: str = Field(..., description="Plan action (scale, rollback, etc.)")
    status: str = Field(..., description="Plan status")
    params: dict[str, Any] = Field(default_factory=dict, description="Plan parameters")


class GraphResponse(BaseModel):
    """Response for /topology/graph endpoint."""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    plans: list[GhostNode] = Field(default_factory=list, description="Pending plans as ghost nodes")


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
    # Plan lifecycle events
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    PLAN_EXECUTED = "plan_executed"
    PLAN_FAILED = "plan_failed"
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
    
    Combines Structure + Metadata + Plans for AI reasoning.
    """
    topology: TopologySnapshot = Field(default_factory=TopologySnapshot)
    services: dict[str, Service] = Field(default_factory=dict, description="service_name -> Service")
    pending_plans: list[Plan] = Field(default_factory=list)


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
