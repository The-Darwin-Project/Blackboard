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
    MetricPoint,
    MetricSeries,
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
    
    async def generate_mermaid(self) -> str:
        """
        Generate Mermaid diagram from topology.
        
        Returns a graph TD syntax string.
        """
        topology = await self.get_topology()
        
        if not topology.services:
            return "graph TD\n    Empty[No services registered]"
        
        lines = ["graph TD"]
        
        # Add edges
        for source, targets in topology.edges.items():
            for target in targets:
                # Sanitize node names (replace - with _)
                src_id = source.replace("-", "_")
                tgt_id = target.replace("-", "_")
                lines.append(f"    {src_id}[{source}] --> {tgt_id}[{target}]")
        
        # Add isolated nodes (services with no edges)
        connected = set()
        for source, targets in topology.edges.items():
            connected.add(source)
            connected.update(targets)
        
        for service in topology.services:
            if service not in connected:
                svc_id = service.replace("-", "_")
                lines.append(f"    {svc_id}[{service}]")
        
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
        
        # Record event
        await self.record_event(EventType.PLAN_CREATED, {"plan_id": plan.id})
        
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
            await self.add_edge(payload.service, dep.target)
        
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
