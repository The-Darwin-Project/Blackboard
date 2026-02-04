# BlackBoard/src/state/blackboard.py
"""
Blackboard State Repository - Central state management for Darwin Brain.

Implements the Blackboard Pattern with three layers:
- Structure Layer: Topology graph (services and edges)
- Metadata Layer: Service health and version info
- Plan Layer: Infrastructure modification plans

Redis Schema (Flat Keys - PoC Simple):
    darwin:services                     SET     [service names]
    darwin:edges:{service}              SET     [dependency names]
    darwin:edge:{source}:{target}       HASH    {protocol, type, env_var, created_at}
    darwin:service:{name}               HASH    {version, cpu, memory, error_rate, last_seen}
    darwin:metrics:{service}:{metric}   ZSET    {timestamp: value}
    darwin:plans                        SET     [plan ids]
    darwin:plan:{id}                    HASH    {plan fields}
    darwin:events                       ZSET    {timestamp: event_json}
"""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, List, Optional

from ..models import (
    ArchitectureEvent,
    ChartData,
    EventType,
    GhostNode,
    GraphEdge,
    GraphNode,
    GraphResponse,
    HealthStatus,
    MetricPoint,
    MetricSeries,
    NodeType,
    Plan,
    PlanCreate,
    PlanStatus,
    Service,
    Snapshot,
    TelemetryPayload,
    TopologySnapshot,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Retention period for metrics history (1 hour for PoC)
METRICS_RETENTION_SECONDS = 3600

# Health thresholds
CPU_WARNING = 60.0
CPU_CRITICAL = 80.0
MEMORY_WARNING = 70.0
MEMORY_CRITICAL = 85.0
ERROR_CRITICAL = 5.0
ZOMBIE_THRESHOLD = 30.0  # seconds without telemetry


def infer_node_type(service_name: str) -> NodeType:
    """
    Infer node type from service name.
    
    Used to determine the visual shape/icon for the node in the graph.
    
    Args:
        service_name: Name of the service
    
    Returns:
        NodeType enum value
    """
    name_lower = service_name.lower()
    
    # Database patterns
    if any(db in name_lower for db in ["postgres", "mysql", "mongo", "db", "database", "mariadb"]):
        return NodeType.DATABASE
    
    # Cache patterns
    if any(cache in name_lower for cache in ["redis", "memcache", "cache", "elasticache"]):
        return NodeType.CACHE
    
    # External service patterns
    if any(ext in name_lower for ext in ["stripe", "twilio", "aws", "gcp", "azure", "external", "api"]):
        return NodeType.EXTERNAL
    
    return NodeType.SERVICE


def calculate_health_status(
    cpu: float,
    memory: float,
    error_rate: float = 0.0,
    last_seen: float = 0.0,
) -> str:
    """
    Calculate health status from metrics.
    
    Shared utility used by both Mermaid and Cytoscape graph generation.
    
    Args:
        cpu: CPU usage percentage (0-100)
        memory: Memory usage percentage (0-100)
        error_rate: Error rate percentage (0-100)
        last_seen: Unix timestamp of last telemetry
    
    Returns:
        'healthy', 'warning', 'critical', or 'unknown'
    """
    # Check for zombie (no recent telemetry)
    if last_seen and (time.time() - last_seen) > ZOMBIE_THRESHOLD:
        return "unknown"
    
    # Critical conditions
    if cpu >= CPU_CRITICAL or memory >= MEMORY_CRITICAL or error_rate >= ERROR_CRITICAL:
        return "critical"
    
    # Warning conditions
    if cpu >= CPU_WARNING or memory >= MEMORY_WARNING:
        return "warning"
    
    return "healthy"


class BlackboardState:
    """
    Repository for Blackboard state operations.
    
    Agents interact with this class, never directly with Redis.
    """
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    # =========================================================================
    # Structure Layer (Topology Graph)
    # =========================================================================
    
    async def add_service(self, name: str) -> None:
        """Add a service node to the topology."""
        await self.redis.sadd("darwin:services", name)
        logger.debug(f"Added service: {name}")
    
    async def add_edge(self, source: str, target: str) -> None:
        """Add a dependency edge from source to target."""
        await self.redis.sadd(f"darwin:edges:{source}", target)
        logger.debug(f"Added edge: {source} -> {target}")
    
    async def add_edge_with_metadata(
        self,
        source: str,
        target: str,
        protocol: str = "HTTP",
        dep_type: str = "hard",
        env_var: Optional[str] = None,
    ) -> None:
        """
        Store edge with full metadata for rich graph visualization.
        
        Args:
            source: Source service name
            target: Target service name
            protocol: Wire protocol (HTTP, SQL, REDIS, gRPC, etc.)
            dep_type: Dependency type ('hard' or 'async')
            env_var: Environment variable name for this dependency
        """
        # Keep backward-compat SET for listing
        await self.redis.sadd(f"darwin:edges:{source}", target)
        
        # Store rich metadata in hash
        edge_key = f"darwin:edge:{source}:{target}"
        await self.redis.hset(edge_key, mapping={
            "protocol": protocol,
            "type": dep_type,
            "env_var": env_var or "",
            "created_at": str(time.time()),
        })
        logger.debug(f"Added edge with metadata: {source} -> {target} ({protocol})")
    
    async def get_edge_metadata(self, source: str, target: str) -> dict:
        """
        Get edge metadata, with fallback for legacy edges.
        
        Returns dict with protocol, type, env_var fields.
        """
        edge_key = f"darwin:edge:{source}:{target}"
        data = await self.redis.hgetall(edge_key)
        if data:
            return data
        # Fallback: infer protocol from target service type
        return {
            "protocol": self._infer_protocol(target),
            "type": "hard",
            "env_var": "",
        }
    
    def _infer_protocol(self, service_name: str) -> str:
        """Infer protocol from service name for legacy edges."""
        name = service_name.lower()
        if any(db in name for db in ["postgres", "mysql", "mongo"]):
            return "SQL"
        if any(c in name for c in ["redis", "memcache"]):
            return "REDIS"
        return "HTTP"
    
    def _infer_protocol_from_type(self, dep_type: str) -> str:
        """
        Map Dependency.type to wire protocol.
        
        Args:
            dep_type: Dependency type from telemetry (db, http, cache, etc.)
        
        Returns:
            Protocol string (SQL, HTTP, REDIS, gRPC, etc.)
        """
        TYPE_TO_PROTOCOL = {
            "db": "SQL",
            "postgres": "SQL",
            "mysql": "SQL",
            "mongo": "MONGO",
            "cache": "REDIS",
            "redis": "REDIS",
            "http": "HTTP",
            "grpc": "gRPC",
            "queue": "AMQP",
            "kafka": "KAFKA",
        }
        return TYPE_TO_PROTOCOL.get(dep_type.lower(), "TCP")
    
    async def get_services(self) -> list[str]:
        """Get all service names."""
        return list(await self.redis.smembers("darwin:services"))
    
    async def get_edges(self, service: str) -> list[str]:
        """Get all dependencies for a service."""
        return list(await self.redis.smembers(f"darwin:edges:{service}"))
    
    async def get_topology(self) -> TopologySnapshot:
        """Get complete topology snapshot."""
        services = await self.get_services()
        edges: dict[str, list[str]] = {}
        
        for service in services:
            deps = await self.get_edges(service)
            if deps:
                edges[service] = deps
        
        return TopologySnapshot(services=services, edges=edges)
    
    async def get_graph_data(self) -> GraphResponse:
        """
        Get topology as rich graph data for Cytoscape.js visualization.
        
        Combines:
        - Services with health status and metadata
        - Edges with protocol information
        - Pending plans as ghost nodes
        
        Returns:
            GraphResponse with nodes, edges, and ghost nodes
        """
        topology = await self.get_topology()
        
        # Build nodes with health status
        nodes: list[GraphNode] = []
        for service_name in topology.services:
            metadata = await self.get_service(service_name)
            metrics = await self.get_current_metrics(service_name)
            
            cpu = metrics.get("cpu", 0)
            memory = metrics.get("memory", 0)
            error_rate = metrics.get("error_rate", 0)
            last_seen = metadata.last_seen if metadata else 0
            version = metadata.version if metadata else "unknown"
            
            health = calculate_health_status(cpu, memory, error_rate, last_seen)
            node_type = infer_node_type(service_name)
            
            nodes.append(GraphNode(
                id=service_name,
                type=node_type,
                label=service_name,
                metadata={
                    "version": version,
                    "health": health,
                    "cpu": cpu,
                    "memory": memory,
                    "error_rate": error_rate,
                    "last_seen": last_seen,
                }
            ))
        
        # Build edges with protocol metadata
        edges: list[GraphEdge] = []
        for source, targets in topology.edges.items():
            for target in targets:
                edge_meta = await self.get_edge_metadata(source, target)
                edges.append(GraphEdge(
                    source=source,
                    target=target,
                    protocol=edge_meta.get("protocol", "HTTP"),
                    type=edge_meta.get("type", "hard"),
                ))
        
        # Build ghost nodes from pending plans (only if target exists in graph)
        plans = await self.get_pending_plans()
        ghost_nodes: list[GhostNode] = []
        known_services = {n.id for n in nodes}  # Set of known service IDs
        
        for plan in plans:
            # Only include ghost nodes if target service exists in the graph
            if plan.service in known_services:
                ghost_nodes.append(GhostNode(
                    plan_id=plan.id,
                    target_node=plan.service,
                    action=plan.action.value,
                    status=plan.status.value,
                    params=plan.params,
                ))
            else:
                logger.warning(
                    f"Skipping ghost node for plan {plan.id}: "
                    f"target service '{plan.service}' not in graph"
                )
        
        return GraphResponse(nodes=nodes, edges=edges, plans=ghost_nodes)
    
    async def generate_mermaid(self) -> str:
        """
        Generate Mermaid diagram from topology with health-based colors.
        
        Returns a graph TD syntax string with:
        - Node labels showing service name and version
        - Node colors based on CPU/memory load (green/yellow/red)
        """
        topology = await self.get_topology()
        
        if not topology.services:
            return "graph TD\n    Empty[No services registered]"
        
        # Get metrics and metadata for all services
        service_data: dict[str, dict] = {}
        for service in topology.services:
            metrics = await self.get_current_metrics(service)
            metadata = await self.get_service(service)
            version = metadata.version if metadata else "?"
            
            # Use shared health calculation
            cpu = metrics.get("cpu", 0)
            memory = metrics.get("memory", 0)
            error_rate = metrics.get("error_rate", 0)
            last_seen = metadata.last_seen if metadata else 0
            status = calculate_health_status(cpu, memory, error_rate, last_seen)
            
            service_data[service] = {
                "version": version,
                "cpu": cpu,
                "memory": memory,
                "status": status,
            }
        
        lines = ["graph TD"]
        
        # Track which nodes we've defined (to avoid duplicates)
        defined_nodes: set[str] = set()
        
        def get_node_def(service: str) -> str:
            """Generate node definition with version and metrics."""
            svc_id = service.replace("-", "_")
            data = service_data.get(service, {"version": "?", "cpu": 0, "memory": 0, "status": "healthy"})
            version = data["version"]
            cpu = data["cpu"]
            memory = data["memory"]
            # Show version and current load
            label = f"{service}<br/>v{version}<br/>CPU:{cpu:.0f}% MEM:{memory:.0f}%"
            return f"{svc_id}[\"{label}\"]"
        
        # Add edges with node definitions
        for source, targets in topology.edges.items():
            for target in targets:
                src_def = get_node_def(source) if source not in defined_nodes else source.replace("-", "_")
                tgt_def = get_node_def(target) if target not in defined_nodes else target.replace("-", "_")
                
                lines.append(f"    {src_def} --> {tgt_def}")
                defined_nodes.add(source)
                defined_nodes.add(target)
        
        # Add isolated nodes (services with no edges)
        connected = set()
        for source, targets in topology.edges.items():
            connected.add(source)
            connected.update(targets)
        
        for service in topology.services:
            if service not in connected and service not in defined_nodes:
                lines.append(f"    {get_node_def(service)}")
                defined_nodes.add(service)
        
        # Add style classes for health status
        lines.append("")
        lines.append("    %% Health-based styling")
        lines.append("    classDef healthy fill:#22c55e,stroke:#166534,color:#fff")
        lines.append("    classDef warning fill:#eab308,stroke:#a16207,color:#000")
        lines.append("    classDef critical fill:#ef4444,stroke:#dc2626,color:#fff")
        lines.append("    classDef unknown fill:#64748b,stroke:#475569,color:#fff")
        
        # Apply classes to nodes
        for service in topology.services:
            svc_id = service.replace("-", "_")
            data = service_data.get(service, {"status": "unknown"})
            status = data.get("status", "unknown")
            lines.append(f"    class {svc_id} {status}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Metadata Layer (Service Health)
    # =========================================================================
    
    async def update_service_metadata(
        self,
        name: str,
        version: str,
        cpu: float,
        memory: float,
        error_rate: float,
    ) -> None:
        """Update service metadata in Redis hash."""
        key = f"darwin:service:{name}"
        await self.redis.hset(key, mapping={
            "version": version,
            "cpu": str(cpu),
            "memory": str(memory),
            "error_rate": str(error_rate),
            "last_seen": str(time.time()),
        })
        logger.debug(f"Updated metadata for {name}: cpu={cpu}, error_rate={error_rate}")
    
    async def get_service(self, name: str) -> Optional[Service]:
        """Get service metadata."""
        key = f"darwin:service:{name}"
        data = await self.redis.hgetall(key)
        
        if not data:
            return None
        
        deps = await self.get_edges(name)
        
        return Service(
            name=name,
            version=data.get("version", "unknown"),
            metrics={
                "cpu": float(data.get("cpu", 0)),
                "memory": float(data.get("memory", 0)),
                "error_rate": float(data.get("error_rate", 0)),
            },
            dependencies=deps,
            last_seen=float(data.get("last_seen", 0)),
        )
    
    async def get_all_services(self) -> dict[str, Service]:
        """Get metadata for all services."""
        names = await self.get_services()
        services: dict[str, Service] = {}
        
        for name in names:
            service = await self.get_service(name)
            if service:
                services[name] = service
        
        return services
    
    # =========================================================================
    # Metrics History Layer (Time-Series)
    # =========================================================================
    
    async def record_metric(
        self,
        service: str,
        metric: str,
        value: float,
        source: str = "self-reported",
    ) -> None:
        """
        Record a metric value with automatic retention trimming.
        
        Uses ZSET with timestamp as score for time-series queries.
        
        Args:
            service: Service name
            metric: Metric name (cpu, memory, error_rate)
            value: Metric value
            source: Data source ("self-reported" or "kubernetes")
        """
        key = f"darwin:metrics:{service}:{metric}"
        now = time.time()
        
        # Add new value (score=timestamp, member="{timestamp}:{value}:{source}")
        # Using timestamp in member to ensure uniqueness
        await self.redis.zadd(key, {f"{now}:{value}:{source}": now})
        
        # Trim old values (older than retention window)
        cutoff = now - METRICS_RETENTION_SECONDS
        await self.redis.zremrangebyscore(key, "-inf", cutoff)
    
    async def get_metric_history(
        self,
        service: str,
        metric: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[MetricPoint]:
        """Get metric history within time range."""
        key = f"darwin:metrics:{service}:{metric}"
        
        start = start_time if start_time else 0
        end = end_time if end_time else time.time()
        
        # Get values with scores (timestamps)
        results = await self.redis.zrangebyscore(
            key, start, end, withscores=True
        )
        
        points = []
        for member, score in results:
            # Parse value from member
            # Format: "{timestamp}:{value}:{source}" or legacy "{timestamp}:{value}"
            parts = member.split(":")
            if len(parts) >= 2:
                value_str = parts[1]
                points.append(MetricPoint(timestamp=score, value=float(value_str)))
        
        return points
    
    async def get_current_metrics(self, service: str) -> dict[str, float]:
        """Get the most recent metrics for a service."""
        metrics = {}
        
        for metric_name in ["cpu", "memory", "error_rate"]:
            key = f"darwin:metrics:{service}:{metric_name}"
            # Get the most recent value
            results = await self.redis.zrevrange(key, 0, 0, withscores=True)
            if results:
                member, _ = results[0]
                # Parse value from member
                # Format: "{timestamp}:{value}:{source}" or legacy "{timestamp}:{value}"
                parts = member.split(":")
                if len(parts) >= 2:
                    metrics[metric_name] = float(parts[1])
                else:
                    metrics[metric_name] = 0.0
            else:
                metrics[metric_name] = 0.0
        
        return metrics
    
    # =========================================================================
    # Plan Layer
    # =========================================================================
    
    async def create_plan(self, plan_data: PlanCreate) -> Plan:
        """Create a new plan and store in Redis."""
        plan = Plan(
            action=plan_data.action,
            service=plan_data.service,
            params=plan_data.params,
            reason=plan_data.reason,
        )
        
        # Add to plans set
        await self.redis.sadd("darwin:plans", plan.id)
        
        # Store plan data as hash
        key = f"darwin:plan:{plan.id}"
        await self.redis.hset(key, mapping={
            "action": plan.action.value,
            "service": plan.service,
            "params": json.dumps(plan.params),
            "reason": plan.reason,
            "status": plan.status.value,
            "created_at": str(plan.created_at),
            "approved_at": "",
            "executed_at": "",
            "result": "",
        })
        
        # Record event with full plan details for UI visibility
        await self.record_event(EventType.PLAN_CREATED, {
            "plan_id": plan.id,
            "action": plan.action.value,
            "service": plan.service,
            "reason": plan.reason[:200] if plan.reason else "",
            "params": plan.params,
        })
        
        logger.info(f"Created plan: {plan.id} - {plan.action.value} {plan.service}")
        return plan
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        key = f"darwin:plan:{plan_id}"
        data = await self.redis.hgetall(key)
        
        if not data:
            return None
        
        return Plan(
            id=plan_id,
            action=data["action"],
            service=data["service"],
            params=json.loads(data.get("params", "{}")),
            reason=data["reason"],
            status=data["status"],
            created_at=float(data.get("created_at", 0)),
            approved_at=float(data["approved_at"]) if data.get("approved_at") else None,
            executed_at=float(data["executed_at"]) if data.get("executed_at") else None,
            result=data.get("result") or None,
        )
    
    async def update_plan_status(
        self,
        plan_id: str,
        status: PlanStatus,
        result: Optional[str] = None,
    ) -> Optional[Plan]:
        """Update plan status."""
        key = f"darwin:plan:{plan_id}"
        
        updates: dict[str, str] = {"status": status.value}
        
        if status == PlanStatus.APPROVED:
            updates["approved_at"] = str(time.time())
            await self.record_event(EventType.PLAN_APPROVED, {"plan_id": plan_id})
        elif status in (PlanStatus.COMPLETED, PlanStatus.FAILED):
            updates["executed_at"] = str(time.time())
            event_type = EventType.PLAN_EXECUTED if status == PlanStatus.COMPLETED else EventType.PLAN_FAILED
            await self.record_event(event_type, {"plan_id": plan_id, "result": result})
        
        if result:
            updates["result"] = result
        
        await self.redis.hset(key, mapping=updates)
        
        logger.info(f"Updated plan {plan_id} status to {status.value}")
        return await self.get_plan(plan_id)
    
    async def list_plans(self, status: Optional[PlanStatus] = None) -> List[Plan]:
        """List all plans, optionally filtered by status."""
        plan_ids = await self.redis.smembers("darwin:plans")
        plans = []
        
        for plan_id in plan_ids:
            plan = await self.get_plan(plan_id)
            if plan:
                if status is None or plan.status == status:
                    plans.append(plan)
        
        # Sort by created_at descending (newest first)
        plans.sort(key=lambda p: p.created_at, reverse=True)
        return plans
    
    async def get_pending_plans(self) -> list[Plan]:
        """Get all pending plans."""
        return await self.list_plans(status=PlanStatus.PENDING)
    
    # =========================================================================
    # Architecture Events (for correlation)
    # =========================================================================
    
    async def record_event(self, event_type: EventType, details: dict) -> None:
        """Record an architecture event."""
        event = ArchitectureEvent(type=event_type, details=details)
        
        # Store as JSON in sorted set (score = timestamp)
        await self.redis.zadd(
            "darwin:events",
            {json.dumps(event.model_dump()): event.timestamp}
        )
        logger.debug(f"Recorded event: {event_type.value}")
    
    async def get_events_in_range(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[ArchitectureEvent]:
        """Get events within time range."""
        start = start_time if start_time else 0
        end = end_time if end_time else time.time()
        
        results = await self.redis.zrangebyscore("darwin:events", start, end)
        
        events = []
        for event_json in results:
            data = json.loads(event_json)
            events.append(ArchitectureEvent(**data))
        
        return events
    
    # =========================================================================
    # Snapshot (Context for Architect)
    # =========================================================================
    
    async def get_snapshot(self) -> Snapshot:
        """
        Get complete Blackboard snapshot for Architect context.
        
        Combines topology, service metadata, and pending plans.
        """
        topology = await self.get_topology()
        services = await self.get_all_services()
        pending_plans = await self.get_pending_plans()
        
        return Snapshot(
            topology=topology,
            services=services,
            pending_plans=pending_plans,
        )
    
    # =========================================================================
    # Chart Data (for Resources visualization)
    # =========================================================================
    
    async def get_chart_data(
        self,
        services: List[str],
        metrics: Optional[List[str]] = None,
        range_seconds: int = 3600,
    ) -> ChartData:
        """
        Get aggregated data for resources consumption chart.
        
        Returns metric series plus architecture events for correlation.
        """
        if metrics is None:
            metrics = ["cpu", "memory", "error_rate"]
        
        end_time = time.time()
        start_time = end_time - range_seconds
        
        series = []
        for service in services:
            for metric in metrics:
                points = await self.get_metric_history(
                    service, metric, start_time, end_time
                )
                if points:
                    series.append(MetricSeries(
                        service=service,
                        metric=metric,
                        data=points,
                    ))
        
        events = await self.get_events_in_range(start_time, end_time)
        
        return ChartData(series=series, events=events)
    
    # =========================================================================
    # Telemetry Processing (called by Aligner)
    # =========================================================================
    
    async def process_telemetry(self, payload: TelemetryPayload) -> None:
        """
        Process incoming telemetry and update all layers.
        
        Called by the Aligner agent.
        """
        # Update Structure Layer
        await self.add_service(payload.service)
        
        for dep in payload.topology.dependencies:
            await self.add_service(dep.target)
            # Store edge with full metadata for rich graph visualization
            await self.add_edge_with_metadata(
                source=payload.service,
                target=dep.target,
                protocol=self._infer_protocol_from_type(dep.type),
                dep_type="hard" if dep.type in ["db", "http"] else "async",
                env_var=dep.env_var,
            )
        
        # Update Metadata Layer
        await self.update_service_metadata(
            name=payload.service,
            version=payload.version,
            cpu=payload.metrics.cpu,
            memory=payload.metrics.memory,
            error_rate=payload.metrics.error_rate,
        )
        
        # Update Metrics History Layer
        await self.record_metric(payload.service, "cpu", payload.metrics.cpu)
        await self.record_metric(payload.service, "memory", payload.metrics.memory)
        await self.record_metric(payload.service, "error_rate", payload.metrics.error_rate)
        
        # Record telemetry event (low frequency, only for significant changes)
        # Skip for now to avoid event spam
        
        logger.debug(f"Processed telemetry from {payload.service}")
