# BlackBoard/src/state/blackboard.py
# @ai-rules:
# 1. [Constraint]: All Redis mutations use WATCH/MULTI/EXEC. Catch redis.WatchError specifically -- NEVER bare Exception.
# 2. [Pattern]: mark_turns_delivered/evaluated/mark_turn_status follow the pipeline pattern from append_turn.
# 3. [Gotcha]: close_event uses WATCH/MULTI/EXEC to prevent turn loss from concurrent writers.
# 4. [Pattern]: Ops journal (darwin:journal:{service}) is a capped LIST (RPUSH + LTRIM). Brain caches reads with 60s TTL.
# 5. [Pattern]: Journal writes happen in 3 places: Brain._close_and_broadcast(), queue.py close_event_by_user(), Brain._startup_cleanup().
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
    darwin:ip:{ip_address}              STRING  {service_name}  TTL=60s
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from redis.exceptions import WatchError

from ..models import (
    ConversationMessage,
    ConversationTurn,
    ArchitectureEvent,
    ChartData,
    EventDocument,
    EventInput,
    EventStatus,
    EventType,
    GhostNode,
    GraphEdge,
    GraphNode,
    GraphResponse,
    HealthStatus,
    MessageStatus,
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

# Conversation TTL (24 hours)
CONVERSATION_TTL_SECONDS = 86400

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
        # Don't add IP addresses as services - they should only be used for edge resolution
        if self._is_ip_address(name):
            logger.debug(f"Skipping IP address from service set: {name}")
            return
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
        """Get all service names (excluding IP addresses)."""
        all_services = await self.redis.smembers("darwin:services")
        # Filter out IP addresses that may have been added before the filter was in place
        return [s for s in all_services if not self._is_ip_address(s)]
    
    async def get_edges(self, service: str) -> list[str]:
        """Get all dependencies for a service."""
        return list(await self.redis.smembers(f"darwin:edges:{service}"))
    
    # =========================================================================
    # IP-to-Service Mapping (for graph deduplication)
    # =========================================================================
    
    async def register_service_ips(self, service: str, ips: list[str]) -> None:
        """
        Register IP-to-service mapping with 60s TTL.
        
        Refreshed on each telemetry push. Allows correlating IP-based
        dependency targets with named services.
        """
        for ip in ips:
            await self.redis.set(f"darwin:ip:{ip}", service, ex=60)
            logger.debug(f"Registered IP mapping: {ip} -> {service}")
    
    async def resolve_ip_to_service(self, target: str) -> str:
        """
        Resolve IP to service name if mapping exists.
        
        Args:
            target: Dependency target (could be IP or service name)
        
        Returns:
            Resolved service name, or original target if not found
        """
        if self._is_ip_address(target):
            resolved = await self.redis.get(f"darwin:ip:{target}")
            if resolved:
                logger.debug(f"Resolved IP {target} -> {resolved}")
                return resolved
        return target
    
    def _is_ip_address(self, value: str) -> bool:
        """Check if value looks like an IPv4 address."""
        import re
        return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', value))
    
    def _is_external_service(self, name: str, metadata: Optional[Service]) -> bool:
        """
        Check if service is external (dependency target but never sent telemetry).
        
        External services like github.com, api.stripe.com appear only as dependency
        targets. They don't send telemetry so they have no meaningful metadata.
        We detect this by checking:
        1. Has common external TLD (.com, .io, .org, etc.)
        2. Has no meaningful telemetry data (last_seen is 0 or very old)
        """
        # Common external domain TLDs
        external_tlds = ['.com', '.io', '.org', '.net', '.dev', '.cloud', '.app']
        
        # Check if name looks like an external domain
        is_external_domain = any(tld in name.lower() for tld in external_tlds)
        if not is_external_domain:
            return False
        
        # If it has metadata with recent telemetry, it's our internal service
        # (might just have an external-looking name)
        if metadata and metadata.last_seen > 0:
            # Check if service has recent telemetry (within last hour)
            import time
            age_seconds = time.time() - metadata.last_seen
            if age_seconds < 3600:  # Has sent telemetry in last hour
                return False
        
        return True
    
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
        
        # Debug: Log all services being processed
        logger.debug(f"Building graph with {len(topology.services)} services: {sorted(topology.services)}")
        
        # Build nodes with health status
        # Filter out IP addresses and external domains - they should not appear as nodes
        nodes: list[GraphNode] = []
        for service_name in topology.services:
            # Skip IP addresses - they should not be displayed as nodes
            if self._is_ip_address(service_name):
                logger.debug(f"Skipping IP address node: {service_name}")
                continue
            
            # Skip Brain self-monitoring -- Brain should not appear in its own topology
            if service_name in ("darwin-brain", "darwin-blackboard-brain"):
                logger.debug(f"Skipping Brain self-monitoring node: {service_name}")
                continue

            # Skip external domains (services that never sent telemetry)
            # External services like github.com, api.stripe.com only appear as dependency targets
            metadata = await self.get_service(service_name)
            if self._is_external_service(service_name, metadata):
                logger.debug(f"Skipping external service node: {service_name}")
                continue
            metrics = await self.get_current_metrics(service_name)
            
            cpu = metrics.get("cpu", 0)
            memory = metrics.get("memory", 0)
            error_rate = metrics.get("error_rate", 0)
            last_seen = metadata.last_seen if metadata else 0
            version = metadata.version if metadata else "unknown"
            
            health = calculate_health_status(cpu, memory, error_rate, last_seen)
            node_type = infer_node_type(service_name)
            
            # Debug: Log postgres specifically
            if "postgres" in service_name.lower():
                logger.debug(
                    f"Adding postgres node: name={service_name}, type={node_type}, "
                    f"cpu={cpu}, memory={memory}, health={health}"
                )
            
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
                    "gitops_repo": metadata.gitops_repo if metadata else None,
                    "gitops_repo_url": metadata.gitops_repo_url if metadata else None,
                    "gitops_helm_path": metadata.gitops_helm_path if metadata else None,
                    "replicas_ready": metadata.replicas_ready if metadata else None,
                    "replicas_desired": metadata.replicas_desired if metadata else None,
                }
            ))
        
        # Build edges with protocol metadata
        # Only include edges where both source and target are actual services (not IPs)
        edges: list[GraphEdge] = []
        known_service_ids = {n.id for n in nodes}  # Set of valid service node IDs
        
        for source, targets in topology.edges.items():
            # Skip edges from IP addresses
            if self._is_ip_address(source):
                logger.debug(f"Skipping edge from IP address: {source}")
                continue
            
            for target in targets:
                # Resolve IP to service name if possible
                resolved_target = await self.resolve_ip_to_service(target)
                
                # Skip edges to IP addresses that couldn't be resolved
                if self._is_ip_address(resolved_target):
                    logger.debug(f"Skipping edge to unresolved IP address: {resolved_target}")
                    continue
                
                # Only include edge if target exists as a node in the graph
                if resolved_target not in known_service_ids:
                    logger.debug(f"Skipping edge to unknown service: {source} -> {resolved_target}")
                    continue
                
                edge_meta = await self.get_edge_metadata(source, target)
                edges.append(GraphEdge(
                    source=source,
                    target=resolved_target,  # Use resolved name
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
        
        # Debug: Log final graph state
        logger.debug(
            f"Graph response: {len(nodes)} nodes, {len(edges)} edges, {len(ghost_nodes)} ghost nodes. "
            f"Node IDs: {[n.id for n in nodes]}"
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
        gitops_repo: Optional[str] = None,
        gitops_repo_url: Optional[str] = None,
        gitops_helm_path: Optional[str] = None,
    ) -> None:
        """Update service metadata in Redis hash."""
        key = f"darwin:service:{name}"
        mapping = {
            "version": version,
            "cpu": str(cpu),
            "memory": str(memory),
            "error_rate": str(error_rate),
            "last_seen": str(time.time()),
        }
        
        # Add GitOps metadata if provided
        if gitops_repo:
            mapping["gitops_repo"] = gitops_repo
        if gitops_repo_url:
            mapping["gitops_repo_url"] = gitops_repo_url
        if gitops_helm_path:
            mapping["gitops_helm_path"] = gitops_helm_path
        
        await self.redis.hset(key, mapping=mapping)
        logger.debug(f"Updated metadata for {name}: cpu={cpu}, error_rate={error_rate}")
    
    async def update_service_replicas(
        self,
        name: str,
        ready: int,
        desired: int,
    ) -> None:
        """Update service replica count in Redis hash."""
        key = f"darwin:service:{name}"
        await self.redis.hset(key, mapping={
            "replicas_ready": str(ready),
            "replicas_desired": str(desired),
        })
        logger.debug(f"Updated replicas for {name}: {ready}/{desired}")
    
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
            gitops_repo=data.get("gitops_repo"),
            gitops_repo_url=data.get("gitops_repo_url"),
            gitops_helm_path=data.get("gitops_helm_path"),
            replicas_ready=int(data["replicas_ready"]) if data.get("replicas_ready") else None,
            replicas_desired=int(data["replicas_desired"]) if data.get("replicas_desired") else None,
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
        interpolate: bool = True,
    ) -> List[MetricPoint]:
        """
        Get metric history within time range.
        
        Merges data from multiple sources (self-reported, kubernetes) and
        optionally interpolates to fill gaps larger than expected interval.
        """
        key = f"darwin:metrics:{service}:{metric}"
        
        start = start_time if start_time else 0
        end = end_time if end_time else time.time()
        
        # Get values with scores (timestamps)
        results = await self.redis.zrangebyscore(
            key, start, end, withscores=True
        )
        
        # Parse all points, separating by source.
        # Format: "{timestamp}:{value}:{source}" or legacy "{timestamp}:{value}"
        self_reported: dict[float, float] = {}  # timestamp -> value
        kubernetes: dict[float, float] = {}     # timestamp -> value
        
        for member, score in results:
            parts = member.split(":")
            if len(parts) >= 2:
                value = float(parts[1])
                source = parts[2] if len(parts) >= 3 else "self-reported"
                timestamp = round(score, 1)  # Round to 100ms for deduplication
                
                if source == "self-reported":
                    self_reported[timestamp] = value
                else:
                    kubernetes[timestamp] = value
        
        # Source selection: if self-reported data exists, use it exclusively.
        # Interleaving K8s metrics-server averages with instantaneous app values
        # creates sawtooth spikes (K8s reports low averages between high app samples).
        # Fall back to K8s data only when no self-reported data is available.
        if self_reported:
            raw_points = self_reported
        elif kubernetes:
            raw_points = kubernetes
        else:
            raw_points = {}
        
        # Sort by timestamp
        sorted_timestamps = sorted(raw_points.keys())
        
        if not sorted_timestamps:
            return []
        
        points = []
        expected_interval = 10.0  # Expected interval between telemetry samples
        max_gap = expected_interval * 3  # Fill gaps up to 3x expected interval
        
        for i, ts in enumerate(sorted_timestamps):
            value = raw_points[ts]
            points.append(MetricPoint(timestamp=ts, value=value))
            
            # Fill gaps with step-hold (carry last value forward).
            # Sampled metrics represent "this was the value at sample time" --
            # the correct assumption is the value held until the next sample,
            # NOT that it linearly moved to the next value.
            if interpolate and i < len(sorted_timestamps) - 1:
                next_ts = sorted_timestamps[i + 1]
                gap = next_ts - ts
                
                if gap > max_gap:
                    # Step-hold: repeat current value at regular intervals
                    num_fill = int(gap / expected_interval) - 1
                    for j in range(1, min(num_fill + 1, 10)):
                        fill_ts = ts + (j * expected_interval)
                        if fill_ts < next_ts:
                            points.append(MetricPoint(timestamp=fill_ts, value=value))
        
        # Sort final points by timestamp
        points.sort(key=lambda p: p.timestamp)
        
        return points
    
    async def get_current_metrics(self, service: str) -> dict[str, float]:
        """
        Get current metrics for a service using peak-over-30s with source priority.
        
        Returns the peak value from the last 30s of self-reported data (preferred)
        or kubernetes data (fallback). This aligns the graph health color with what
        Flash sees in the 30s analysis window -- if CPU peaked at 99.9% recently,
        the node shows yellow/red, not green from a single low K8s reading.
        """
        metrics = {}
        now = time.time()
        cutoff = now - 30  # 30s window matching the Aligner analysis interval
        
        for metric_name in ["cpu", "memory", "error_rate"]:
            key = f"darwin:metrics:{service}:{metric_name}"
            # Get last 30s of data (score = timestamp)
            results = await self.redis.zrangebyscore(
                key, cutoff, now, withscores=True
            )
            
            if not results:
                # No recent data -- fall back to latest entry regardless of age
                fallback = await self.redis.zrevrange(key, 0, 0, withscores=True)
                if fallback:
                    parts = fallback[0][0].split(":")
                    metrics[metric_name] = float(parts[1]) if len(parts) >= 2 else 0.0
                else:
                    metrics[metric_name] = 0.0
                continue
            
            # Separate by source, find peak value per source
            self_reported_peak = 0.0
            kubernetes_peak = 0.0
            has_self_reported = False
            
            for member, _score in results:
                parts = member.split(":")
                if len(parts) < 2:
                    continue
                value = float(parts[1])
                source = parts[2] if len(parts) >= 3 else "self-reported"
                
                if source == "self-reported":
                    has_self_reported = True
                    self_reported_peak = max(self_reported_peak, value)
                else:
                    kubernetes_peak = max(kubernetes_peak, value)
            
            # Prefer self-reported; fall back to kubernetes
            if has_self_reported:
                metrics[metric_name] = self_reported_peak
            else:
                metrics[metric_name] = kubernetes_peak
        
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
        reason_preview = plan.reason[:100] if plan.reason else "No reason provided"
        await self.record_event(
            EventType.PLAN_CREATED,
            {
                "plan_id": plan.id,
                "action": plan.action.value,
                "service": plan.service,
                "reason": plan.reason[:200] if plan.reason else "",
                "params": plan.params,
            },
            narrative=f"Based on my analysis, I recommend: {plan.action.value} {plan.service}. Reason: {reason_preview}",
        )
        
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
            # Get plan to include service and action in event
            plan = await self.get_plan(plan_id)
            await self.record_event(
                EventType.PLAN_APPROVED,
                {
                    "plan_id": plan_id,
                    "service": plan.service if plan else None,
                    "action": plan.action.value if plan else None,
                },
                narrative=f"Plan approved: {plan.action.value} on {plan.service}" if plan else f"Plan {plan_id} approved",
            )
        elif status in (PlanStatus.COMPLETED, PlanStatus.FAILED):
            updates["executed_at"] = str(time.time())
            plan = await self.get_plan(plan_id)
            
            if status == PlanStatus.COMPLETED:
                await self.record_event(
                    EventType.PLAN_EXECUTED,
                    {
                        "plan_id": plan_id,
                        "service": plan.service if plan else None,
                        "action": plan.action.value if plan else None,
                        "status": "success",
                        "summary": f"{plan.action.value} {plan.service}" if plan else None,
                        "result": result[:500] if result else "",
                    },
                    narrative=f"Successfully executed {plan.action.value} on {plan.service}." if plan else None,
                )
            else:  # FAILED
                await self.record_event(
                    EventType.PLAN_FAILED,
                    {
                        "plan_id": plan_id,
                        "service": plan.service if plan else None,
                        "action": plan.action.value if plan else None,
                        "status": "failed",
                        "error": result[:500] if result else "",
                    },
                    narrative=f"Failed to execute plan for {plan.service}: {result[:100]}" if plan and result else None,
                )
        
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
    
    async def record_event(
        self,
        event_type: EventType,
        details: dict,
        narrative: Optional[str] = None,
    ) -> None:
        """Record an architecture event with optional narrative."""
        event = ArchitectureEvent(
            type=event_type,
            details=details,
            narrative=narrative,
        )
        
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
    # Task Queue Layer (Blackboard-Centric Communication)
    # =========================================================================
    
    # Task queue Redis keys
    TASK_KEY_ARCHITECT = "darwin:tasks:architect"
    TASK_KEY_SYSADMIN = "darwin:tasks:sysadmin"
    
    async def enqueue_architect_task(self, task: dict) -> str:
        """
        DEPRECATED: Use create_event() instead.
        
        Enqueue task for Architect to process.
        
        Used by Aligner to trigger Architect analysis via Blackboard.
        
        Returns task_id.
        """
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task["id"] = task_id
        task["created_at"] = time.time()
        await self.redis.lpush(self.TASK_KEY_ARCHITECT, json.dumps(task))
        logger.debug(f"Enqueued architect task: {task_id}")
        return task_id
    
    async def dequeue_architect_task(self) -> Optional[dict]:
        """
        DEPRECATED: Use dequeue_event() instead.
        
        Dequeue next task for Architect (blocking pop with timeout).
        
        Returns task dict or None if queue is empty after timeout.
        """
        result = await self.redis.brpop(self.TASK_KEY_ARCHITECT, timeout=5)
        if result:
            _, task_json = result
            task = json.loads(task_json)
            logger.debug(f"Dequeued architect task: {task.get('id')}")
            return task
        return None
    
    async def enqueue_plan_for_execution(self, plan_id: str) -> None:
        """
        DEPRECATED: Use event conversation turns instead.
        
        Enqueue approved plan for SysAdmin execution.
        
        Called after plan is approved (either manually or auto-approved).
        """
        await self.redis.lpush(self.TASK_KEY_SYSADMIN, plan_id)
        logger.debug(f"Enqueued plan for execution: {plan_id}")
    
    async def dequeue_plan_for_execution(self) -> Optional[str]:
        """
        DEPRECATED: Use event conversation turns instead.
        
        Dequeue next plan_id for SysAdmin (blocking pop with timeout).
        
        Returns plan_id or None if queue is empty after timeout.
        """
        result = await self.redis.brpop(self.TASK_KEY_SYSADMIN, timeout=5)
        if result:
            _, plan_id = result
            logger.debug(f"Dequeued plan for execution: {plan_id}")
            return plan_id
        return None
    
    async def get_events_for_service(
        self,
        service: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[ArchitectureEvent]:
        """Get events filtered by service name in details."""
        all_events = await self.get_events_in_range(start_time, end_time)
        return [
            e for e in all_events 
            if e.details.get("service") == service
        ]
    
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
        
        logger.debug(f"get_chart_data called for services: {services}, range: {range_seconds}s")
        
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
                    logger.debug(f"Chart data: {service}/{metric} has {len(points)} points")
                else:
                    logger.debug(f"Chart data: {service}/{metric} has NO points")
        
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
        # Register this service's IPs for IP-to-name correlation
        # (before processing dependencies so other services can resolve us)
        if payload.pod_ips:
            await self.register_service_ips(payload.service, payload.pod_ips)
        
        # Update Structure Layer
        await self.add_service(payload.service)
        
        for dep in payload.topology.dependencies:
            # Resolve IP to service name if mapping exists
            resolved_target = await self.resolve_ip_to_service(dep.target)
            await self.add_service(resolved_target)
            # Store edge with full metadata for rich graph visualization
            await self.add_edge_with_metadata(
                source=payload.service,
                target=resolved_target,  # Use resolved name
                protocol=self._infer_protocol_from_type(dep.type),
                dep_type="hard" if dep.type in ["db", "http"] else "async",
                env_var=dep.env_var,
            )
        
        # Update Metadata Layer (including GitOps coordinates if provided)
        await self.update_service_metadata(
            name=payload.service,
            version=payload.version,
            cpu=payload.metrics.cpu,
            memory=payload.metrics.memory,
            error_rate=payload.metrics.error_rate,
            gitops_repo=payload.gitops.repo if payload.gitops else None,
            gitops_repo_url=payload.gitops.repo_url if payload.gitops else None,
            gitops_helm_path=payload.gitops.helm_path if payload.gitops else None,
        )
        
        # Update Metrics History Layer
        await self.record_metric(payload.service, "cpu", payload.metrics.cpu)
        await self.record_metric(payload.service, "memory", payload.metrics.memory)
        await self.record_metric(payload.service, "error_rate", payload.metrics.error_rate)
        
        # Record telemetry event (low frequency, only for significant changes)
        # Skip for now to avoid event spam
        
        logger.debug(f"Processed telemetry from {payload.service}")
    
    # =========================================================================
    # Conversation History Layer
    # =========================================================================
    
    async def create_conversation(self) -> str:
        """
        Create a new conversation and return its ID.
        
        Conversations use Redis HASH with 24-hour TTL.
        """
        conversation_id = str(uuid.uuid4())
        key = f"darwin:conversation:{conversation_id}"
        
        # Initialize with creation timestamp
        await self.redis.hset(key, "created", str(time.time()))
        await self.redis.expire(key, CONVERSATION_TTL_SECONDS)
        
        logger.debug(f"Created conversation: {conversation_id}")
        return conversation_id
    
    async def get_conversation(self, conversation_id: str) -> List[ConversationMessage]:
        """
        Get all messages in a conversation.
        
        Messages are stored as numbered fields (msg:0, msg:1, etc.)
        """
        key = f"darwin:conversation:{conversation_id}"
        data = await self.redis.hgetall(key)
        
        messages = []
        # Extract numbered message fields and sort by index
        msg_keys = sorted(
            [k for k in data.keys() if k.startswith("msg:")],
            key=lambda k: int(k.split(":")[1])
        )
        
        for msg_key in msg_keys:
            msg_data = json.loads(data[msg_key])
            messages.append(ConversationMessage(**msg_data))
        
        return messages
    
    async def append_to_conversation(
        self,
        conversation_id: str,
        message: ConversationMessage,
    ) -> None:
        """
        Append a message to a conversation.
        
        Messages are stored with incrementing indices (msg:0, msg:1, etc.)
        """
        key = f"darwin:conversation:{conversation_id}"
        
        # Get current message count
        data = await self.redis.hgetall(key)
        msg_count = len([k for k in data.keys() if k.startswith("msg:")])
        
        # Add new message
        await self.redis.hset(
            key,
            f"msg:{msg_count}",
            json.dumps(message.model_dump())
        )
        
        # Refresh TTL on each message
        await self.redis.expire(key, CONVERSATION_TTL_SECONDS)
        
        logger.debug(
            f"Appended {message.role} message to conversation {conversation_id}"
        )

    # =========================================================================
    # Event Queue Layer (Conversation Queue System)
    # =========================================================================
    #
    # Redis Schema:
    #     darwin:queue                        LIST    [event IDs awaiting Brain triage]
    #     darwin:event:{id}                   STRING  {JSON EventDocument}
    #     darwin:event:active                 SET     [event IDs currently processing]
    #     darwin:event:closed                 ZSET    {close_timestamp: event_id}
    #     darwin:agent:notify:{agent_name}    LIST    [event IDs for agent attention]
    
    EVENT_QUEUE = "darwin:queue"
    EVENT_PREFIX = "darwin:event:"
    EVENT_ACTIVE = "darwin:event:active"
    EVENT_CLOSED = "darwin:event:closed"
    # AGENT_NOTIFY_PREFIX removed -- WebSocket replaces Redis agent notifications

    # Ops journal -- per-service temporal memory for pattern recognition
    JOURNAL_PREFIX = "darwin:journal:"
    JOURNAL_MAX_ENTRIES = 20

    async def create_event(
        self,
        source: str,
        service: str,
        reason: str,
        evidence: str,
    ) -> str:
        """Create a new event and add to the queue for Brain triage."""
        from datetime import datetime
        event = EventDocument(
            source=source,
            service=service,
            event=EventInput(
                reason=reason,
                evidence=evidence,
                timeDate=datetime.now().isoformat(),
            ),
        )
        # Store event document
        await self.redis.set(
            f"{self.EVENT_PREFIX}{event.id}",
            json.dumps(event.model_dump())
        )
        # Add to active set
        await self.redis.sadd(self.EVENT_ACTIVE, event.id)
        # Push to queue for Brain
        await self.redis.lpush(self.EVENT_QUEUE, event.id)
        logger.info(f"Created event: {event.id} ({source}) for {service}")
        return event.id

    async def get_event(self, event_id: str) -> Optional[EventDocument]:
        """Get an event document by ID."""
        data = await self.redis.get(f"{self.EVENT_PREFIX}{event_id}")
        if not data:
            return None
        return EventDocument(**json.loads(data))

    async def append_turn(
        self,
        event_id: str,
        turn: ConversationTurn,
    ) -> None:
        """Append a conversation turn to an event document."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        # Use WATCH for optimistic locking
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for append_turn")
                        return
                    event = EventDocument(**json.loads(data))
                    event.conversation.append(turn)
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Appended turn {turn.turn} ({turn.actor}.{turn.action}) to event {event_id}")

    async def mark_turns_delivered(
        self,
        event_id: str,
        up_to_turn: int,
    ) -> int:
        """Mark all SENT turns as DELIVERED up to index (exclusive).

        Uses WATCH/MULTI/EXEC for safe concurrent mutation.
        Returns count of turns updated.
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        return 0
                    event = EventDocument(**json.loads(data))
                    changed = 0
                    for t in event.conversation[:up_to_turn]:
                        if t.status == MessageStatus.SENT:
                            t.status = MessageStatus.DELIVERED
                            changed += 1
                    if changed == 0:
                        return 0
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    logger.debug(f"Marked {changed} turns DELIVERED for event {event_id}")
                    return changed
                except WatchError:
                    continue

    async def mark_turns_evaluated(
        self,
        event_id: str,
        up_to_turn: Optional[int] = None,
    ) -> int:
        """Mark SENT/DELIVERED turns as EVALUATED.

        If up_to_turn is given, only marks turns up to that index (exclusive).
        If None, marks all turns. This prevents marking turns that arrive
        during process_event as EVALUATED before the Brain reads them.

        Uses WATCH/MULTI/EXEC for safe concurrent mutation.
        Returns count of turns updated.
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        return 0
                    event = EventDocument(**json.loads(data))
                    scope = event.conversation[:up_to_turn] if up_to_turn is not None else event.conversation
                    changed = 0
                    for t in scope:
                        if t.status in (MessageStatus.SENT, MessageStatus.DELIVERED):
                            t.status = MessageStatus.EVALUATED
                            changed += 1
                    if changed == 0:
                        return 0
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    logger.debug(f"Marked {changed} turns EVALUATED for event {event_id}")
                    return changed
                except WatchError:
                    continue

    async def mark_turn_status(
        self,
        event_id: str,
        turn_number: int,
        status: "MessageStatus",
    ) -> bool:
        """Update a single turn's status by turn number.

        Used for agent-side tracking of brain.route turns.
        Returns True if updated, False if turn not found.
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        return False
                    event = EventDocument(**json.loads(data))
                    found = False
                    for t in event.conversation:
                        if t.turn == turn_number:
                            t.status = status
                            found = True
                            break
                    if not found:
                        return False
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    logger.debug(f"Marked turn {turn_number} as {status.value} for event {event_id}")
                    return True
                except WatchError:
                    continue

    async def transition_event_status(
        self,
        event_id: str,
        from_status: str,
        to_status: "EventStatus",
    ) -> bool:
        """Atomically transition an event's status using WATCH/MULTI/EXEC.

        Returns True if the transition succeeded, False if the current status
        didn't match from_status (no-op).
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for status transition")
                        return False
                    event = EventDocument(**json.loads(data))
                    if event.status.value != from_status:
                        logger.debug(f"Event {event_id} status is '{event.status.value}', expected '{from_status}' -- skipping transition")
                        return False
                    event.status = to_status
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.info(f"Event {event_id} status: {from_status} -> {to_status.value}")
        return True

    # NOTE: notify_agent and dequeue_agent_notification REMOVED.
    # Agent communication now uses WebSocket (Brain -> Agent direct).
    # Redis agent notification queues (darwin:agent:notify:*) are no longer used.

    async def dequeue_event(self) -> Optional[str]:
        """Dequeue next event_id from the Brain queue (blocking pop with timeout)."""
        result = await self.redis.brpop(self.EVENT_QUEUE, timeout=5)
        if result:
            _, event_id = result
            logger.debug(f"Dequeued event: {event_id}")
            return event_id
        return None

    async def get_active_events(self) -> list[str]:
        """Get all active event IDs."""
        return list(await self.redis.smembers(self.EVENT_ACTIVE))

    async def get_recent_closed_for_service(
        self, service: str, minutes: int = 15
    ) -> list[tuple[str, float, str]]:
        """Get recently closed events for a service.
        Returns list of (event_id, close_timestamp, closing_summary).

        Uses withscores + pipeline to avoid N+1 Redis roundtrips.
        """
        cutoff = time.time() - (minutes * 60)
        # Single ZRANGEBYSCORE with scores -- no separate zscore() calls needed
        closed_with_scores: list[tuple[str, float]] = await self.redis.zrangebyscore(
            self.EVENT_CLOSED, cutoff, time.time(), withscores=True
        )
        if not closed_with_scores:
            return []

        # Pipeline: batch-GET all event documents in one roundtrip
        async with self.redis.pipeline(transaction=False) as pipe:
            for eid, _ in closed_with_scores:
                pipe.get(f"{self.EVENT_PREFIX}{eid}")
            docs = await pipe.execute()

        results = []
        for (eid, close_time), raw in zip(closed_with_scores, docs):
            if not raw:
                continue
            event = EventDocument(**json.loads(raw))
            if event.service != service:
                continue
            # Get closing summary from last turn
            summary = ""
            if event.conversation:
                last = event.conversation[-1]
                summary = (last.thoughts or last.result or "")[:150]
            results.append((eid, close_time, summary))
        return results

    async def append_journal(self, service: str, entry: str) -> None:
        """Append a one-line ops journal entry for a service."""
        from datetime import datetime
        key = f"{self.JOURNAL_PREFIX}{service}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        await self.redis.rpush(key, f"[{timestamp}] {entry}")
        await self.redis.ltrim(key, -self.JOURNAL_MAX_ENTRIES, -1)

    async def get_journal(self, service: str) -> list[str]:
        """Get all ops journal entries for a service (newest last)."""
        key = f"{self.JOURNAL_PREFIX}{service}"
        return await self.redis.lrange(key, 0, -1)

    async def close_event(self, event_id: str, summary: str) -> None:
        """Close an event with summary. Move from active to closed.

        Uses WATCH/MULTI/EXEC to prevent losing turns appended between
        GET and SET by concurrent writers (mark_turns_*, append_turn).
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        break
                    event = EventDocument(**json.loads(data))
                    event.status = EventStatus.CLOSED
                    # Append closing turn
                    close_turn = ConversationTurn(
                        turn=len(event.conversation) + 1,
                        actor="brain",
                        action="close",
                        thoughts=summary,
                    )
                    event.conversation.append(close_turn)
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        # Move from active to closed
        await self.redis.srem(self.EVENT_ACTIVE, event_id)
        await self.redis.zadd(self.EVENT_CLOSED, {event_id: time.time()})
        logger.info(f"Closed event: {event_id}")
