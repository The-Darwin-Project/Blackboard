# BlackBoard/src/state/blackboard.py
# @ai-rules:
# 1. [Constraint]: Redis mutations use WATCH/MULTI/EXEC or Lua scripts for atomicity. Catch redis.WatchError specifically -- NEVER bare Exception.
# 2. [Pattern]: mark_turns_delivered/evaluated/mark_turn_status/update_turn_evidence follow the pipeline pattern from append_turn.
# 3. [Gotcha]: close_event uses WATCH/MULTI/EXEC to prevent turn loss from concurrent writers.
# 4. [Pattern]: Ops journal (darwin:journal:{service}) is a capped LIST (RPUSH + LTRIM). Brain caches reads with 60s TTL.
# 5. [Pattern]: Journal writes happen in 3 places: Brain._close_and_broadcast(), queue.py close_event_by_user(), Brain._startup_cleanup().
# 6. [Pattern]: _should_include_service() is the shared node filter for BOTH get_graph_data() and generate_mermaid(). Ticket nodes bypass this filter -- they are loaded via _get_ticket_nodes() from active events, not from the K8s topology.
# 7. [Pattern]: Slack thread mapping (darwin:slack:thread:{channel_id}:{thread_ts}) is cleaned up by delete_slack_mapping() on event close.
# 8. [Pattern]: create_event() accepts optional created_by_email for multi-tenant event ownership. Callers (chat WS) pass user.email; automated sources default to None.
# 9. [Pattern]: update_event_sticky_notes() follows same WATCH/MULTI as all update_event_* methods.
# 10. [Pattern]: Lua scripts registered once at __init__ via register_script() — used for atomic compare-and-delete (escalation flag).
# 11. [Pattern]: Field Notes Notebook (darwin:notebook HASH). RENAMENX for atomic drain; ResponseError for missing-source guard. Quarantine via RENAME after MAX_DIGEST_RETRIES. Retry counter is Redis INCR with TTL (survives pod restart).
"""
Blackboard State Repository - Central state management for Darwin Brain.

Implements the Blackboard Pattern with two layers:
- Structure Layer: Topology graph (services and edges)
- Metadata Layer: Service health and version info

Redis Schema (Flat Keys - PoC Simple):
    darwin:services                     SET     [service names]
    darwin:edges:{service}              SET     [dependency names]
    darwin:edge:{source}:{target}       HASH    {protocol, type, env_var, created_at}
    darwin:service:{name}               HASH    {version, cpu, memory, error_rate, last_seen}
    darwin:metrics:{service}:{metric}   ZSET    {timestamp: value}
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

from redis.exceptions import ResponseError, WatchError

from ..models import (
    ConversationMessage,
    ConversationTurn,
    ArchitectureEvent,
    ChartData,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    EventType,
    GraphEdge,
    GraphNode,
    GraphResponse,
    HealthStatus,
    MessageStatus,
    MetricPoint,
    MetricSeries,
    NodeType,
    Service,
    Snapshot,
    TelemetryPayload,
    TicketNode,
    TopologySnapshot,
    _resolve_phase,
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
ZOMBIE_THRESHOLD = 90.0  # seconds without telemetry (3x observer interval to avoid flicker)


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
    
    _LUA_CLEAR_ESCALATION = """
local val = redis.call('HGET', KEYS[1], 'escalation_flag')
if not val or val == '' then return 0 end
local delim = string.find(val, '|')
local prefix = delim and string.sub(val, 1, delim - 1) or val
if prefix == ARGV[1] then
    redis.call('HDEL', KEYS[1], 'escalation_flag')
    return 1
end
return 0
"""

    def __init__(self, redis: Redis):
        self.redis = redis
        self._clear_escalation_script = self.redis.register_script(
            self._LUA_CLEAR_ESCALATION
        )
    
    # =========================================================================
    # Structure Layer (Topology Graph)
    # =========================================================================
    
    async def add_service(self, name: str) -> None:
        """Add a service node to the topology."""
        if not name or not name.strip():
            logger.debug("Skipping empty/whitespace service name")
            return
        # Don't add IP addresses as services - they should only be used for edge resolution
        if self._is_ip_address(name):
            logger.debug(f"Skipping IP address from service set: {name}")
            return
        await self.redis.sadd("darwin:services", name)
        logger.debug(f"Added service: {name}")
    
    async def remove_service(self, name: str) -> int:
        """
        Remove a stale service and all its associated data from the topology.

        Cleans: service set membership, metadata hash, outbound edges,
        inbound edge references from other services, and edge metadata.

        Returns the number of Redis keys deleted.
        """
        if not name or not name.strip():
            return 0
        deleted = 0
        # Remove from service set
        deleted += await self.redis.srem("darwin:services", name)
        # Remove metadata hash
        deleted += await self.redis.delete(f"darwin:service:{name}")
        # Remove outbound edges set and their metadata
        outbound = await self.redis.smembers(f"darwin:edges:{name}")
        for target in outbound:
            await self.redis.delete(f"darwin:edge:{name}:{target}")
            deleted += 1
        deleted += await self.redis.delete(f"darwin:edges:{name}")
        # Remove inbound edge references from all other services
        all_services = await self.redis.smembers("darwin:services")
        for other in all_services:
            removed = await self.redis.srem(f"darwin:edges:{other}", name)
            if removed:
                await self.redis.delete(f"darwin:edge:{other}:{name}")
                deleted += removed + 1
        logger.info(f"Removed stale service '{name}' ({deleted} keys cleaned)")
        return deleted

    async def add_edge(self, source: str, target: str) -> None:
        """Add a dependency edge from source to target."""
        if not source or not source.strip() or not target or not target.strip():
            logger.debug(f"Skipping edge with empty source/target: '{source}' -> '{target}'")
            return
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
        if not source or not source.strip() or not target or not target.strip():
            logger.debug(f"Skipping edge_with_metadata with empty source/target: '{source}' -> '{target}'")
            return
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
        """Get all service names (excluding IPs, empty strings, bare ports)."""
        all_services = await self.redis.smembers("darwin:services")
        # Filter out phantom entries that may exist in Redis from before ingestion guards
        return [s for s in all_services
                if s and s.strip()
                and not self._is_ip_address(s)
                and not self._is_bare_port(s)]
    
    async def get_edges(self, service: str) -> list[str]:
        """Get all dependencies for a service (excluding empty strings, bare ports)."""
        raw = await self.redis.smembers(f"darwin:edges:{service}")
        return [t for t in raw if t and t.strip() and not self._is_bare_port(t)]
    
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
    
    def _is_bare_port(self, value: str) -> bool:
        """Check if value is a bare port number (e.g., '5432', '6379')."""
        return value.isdigit() and 0 < int(value) <= 65535
    
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
    
    def _should_include_service(self, name: str, metadata: Optional[Service]) -> bool:
        """
        Shared filter for topology graph consumers.
        
        Returns True if the service should appear as a node in both the
        Cytoscape graph and Mermaid diagram.  Centralises the filtering
        logic so get_graph_data() and generate_mermaid() stay in sync.
        """
        if not name or not name.strip():
            return False
        if self._is_ip_address(name):
            return False
        if self._is_bare_port(name):
            return False
        if name in ("darwin-brain", "darwin-blackboard-brain"):
            return False
        if self._is_external_service(name, metadata):
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
        - Ticket nodes from active events
        
        Returns:
            GraphResponse with nodes, edges, and ticket nodes
        """
        topology = await self.get_topology()
        
        # Debug: Log all services being processed
        logger.debug(f"Building graph with {len(topology.services)} services: {sorted(topology.services)}")
        
        # Build nodes with health status
        # Filter using shared _should_include_service() predicate
        nodes: list[GraphNode] = []
        for service_name in topology.services:
            metadata = await self.get_service(service_name)
            if not self._should_include_service(service_name, metadata):
                logger.debug(f"Skipping filtered service node: {service_name}")
                continue
            metrics = await self.get_current_metrics(service_name)
            
            cpu = metrics.get("cpu", 0)
            memory = metrics.get("memory", 0)
            error_rate = metrics.get("error_rate", 0)
            last_seen = metadata.last_seen if metadata else 0
            version = metadata.version if metadata else "unknown"
            
            health = calculate_health_status(cpu, memory, error_rate, last_seen)
            node_type = infer_node_type(service_name)
            
            # Log any service that resolves to "unknown" -- helps debug gray nodes
            if health == "unknown":
                age = time.time() - last_seen if last_seen else -1
                logger.warning(
                    f"Gray node detected: {service_name} health=unknown, "
                    f"last_seen={last_seen:.0f} (age={age:.0f}s), "
                    f"cpu={cpu}, memory={memory}, error_rate={error_rate}"
                )
            
            icon = await self.redis.hget(f"darwin:service:{service_name}", "icon")

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
                    "source_repo_url": metadata.source_repo_url if metadata else None,
                    "gitops_repo": metadata.gitops_repo if metadata else None,
                    "gitops_repo_url": metadata.gitops_repo_url if metadata else None,
                    "gitops_config_path": metadata.gitops_config_path if metadata else None,
                    "replicas_ready": metadata.replicas_ready if metadata else None,
                    "replicas_desired": metadata.replicas_desired if metadata else None,
                    "escalation_flag": metadata.escalation_flag if metadata else None,
                    "icon": icon,
                }
            ))
        
        # Build edges with protocol metadata
        # Only include edges where both source and target are actual services (not IPs)
        edges: list[GraphEdge] = []
        known_service_ids = {n.id for n in nodes}  # Set of valid service node IDs
        
        for source, targets in topology.edges.items():
            # Skip empty source -- prevents Cytoscape empty ID crash
            if not source or not source.strip():
                logger.debug("Skipping edge with empty source in graph edge loop")
                continue
            # Skip edges from IP addresses
            if self._is_ip_address(source):
                logger.debug(f"Skipping edge from IP address: {source}")
                continue
            # Only include edge if source exists as a node in the graph
            if source not in known_service_ids:
                logger.debug(f"Skipping edge from filtered-out source: {source}")
                continue
            
            for target in targets:
                if not target or not target.strip():
                    logger.debug("Skipping edge with empty target in graph edge loop")
                    continue
                # Resolve IP to service name if possible
                resolved_target = await self.resolve_ip_to_service(target)
                
                # Skip empty resolved targets -- prevents Cytoscape empty ID crash
                if not resolved_target or not resolved_target.strip():
                    logger.debug(f"Skipping edge with empty resolved target for: {target}")
                    continue
                
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
        
        # Build ticket nodes from active general/headhunter events
        ticket_nodes = await self._get_ticket_nodes()

        logger.debug(
            f"Graph response: {len(nodes)} nodes, {len(edges)} edges, "
            f"{len(ticket_nodes)} ticket nodes. "
            f"Node IDs: {[n.id for n in nodes]}"
        )
        
        return GraphResponse(nodes=nodes, edges=edges, tickets=ticket_nodes)
    
    async def generate_mermaid(self) -> str:
        """
        Generate Mermaid diagram from topology with health-based colors.
        
        Applies the same filtering as get_graph_data() via
        _should_include_service() so phantom nodes (empty strings,
        bare ports, IPs, Brain, externals) never appear in Mermaid output.
        
        Returns a graph TD syntax string with:
        - Node labels showing service name and version
        - Node colors based on CPU/memory load (green/yellow/red)
        """
        topology = await self.get_topology()
        
        if not topology.services:
            return "graph TD\n    Empty[No services registered]"
        
        # ── Filter services using the shared predicate ──
        # Fetch metadata first (needed by the filter) then build
        # service_data only for included services.
        filtered_services: set[str] = set()
        service_data: dict[str, dict] = {}
        
        for service in topology.services:
            metadata = await self.get_service(service)
            if not self._should_include_service(service, metadata):
                logger.debug(f"Mermaid: skipping filtered service: {service}")
                continue
            
            filtered_services.add(service)
            metrics = await self.get_current_metrics(service)
            version = metadata.version if metadata else "?"
            
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
        
        if not filtered_services:
            return "graph TD\n    Empty[No services registered]"
        
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
            label = f"{service}<br/>v{version}<br/>CPU:{cpu:.0f}% MEM:{memory:.0f}%"
            return f"{svc_id}[\"{label}\"]"
        
        # ── Add edges -- only where both source and target are included ──
        for source, targets in topology.edges.items():
            if source not in filtered_services:
                continue
            for target in targets:
                if target not in filtered_services:
                    continue
                src_def = get_node_def(source) if source not in defined_nodes else source.replace("-", "_")
                tgt_def = get_node_def(target) if target not in defined_nodes else target.replace("-", "_")
                
                lines.append(f"    {src_def} --> {tgt_def}")
                defined_nodes.add(source)
                defined_nodes.add(target)
        
        # Add isolated nodes (filtered services with no edges)
        connected = set()
        for source, targets in topology.edges.items():
            if source in filtered_services:
                connected.add(source)
                connected.update(t for t in targets if t in filtered_services)
        
        for service in filtered_services:
            if service not in connected and service not in defined_nodes:
                lines.append(f"    {get_node_def(service)}")
                defined_nodes.add(service)
        
        # Add ticket nodes from active general/headhunter events
        ticket_nodes = await self._get_ticket_nodes()
        ticket_ids: list[str] = []
        for ticket in ticket_nodes:
            tid = f"ticket_{ticket.event_id.replace('-', '_')}"
            ticket_ids.append(tid)
            agent = ticket.current_agent or "pending"
            label = f"{ticket.event_id}<br/>{ticket.status} | {agent}<br/>turns: {ticket.turn_count}"
            lines.append(f'    {tid}["{label}"]')

        # Add style classes for health status
        lines.append("")
        lines.append("    %% Health-based styling")
        lines.append("    classDef healthy fill:#22c55e,stroke:#166534,color:#fff")
        lines.append("    classDef warning fill:#eab308,stroke:#a16207,color:#000")
        lines.append("    classDef critical fill:#ef4444,stroke:#dc2626,color:#fff")
        lines.append("    classDef unknown fill:#64748b,stroke:#475569,color:#fff")
        lines.append("    classDef ticket fill:#f59e0b,stroke:#d97706,color:#000")
        
        # Apply classes only to filtered nodes
        for service in filtered_services:
            svc_id = service.replace("-", "_")
            data = service_data.get(service, {"status": "unknown"})
            status = data.get("status", "unknown")
            lines.append(f"    class {svc_id} {status}")

        for tid in ticket_ids:
            lines.append(f"    class {tid} ticket")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Metadata Layer (Service Health)
    # =========================================================================
    
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
    ) -> None:
        """Update service metadata in Redis hash. Version and error_rate only written when provided."""
        key = f"darwin:service:{name}"
        mapping: dict[str, str] = {
            "cpu": str(cpu),
            "memory": str(memory),
            "last_seen": str(time.time()),
        }
        if error_rate is not None:
            mapping["error_rate"] = str(error_rate)
        if version is not None:
            mapping["version"] = version
        
        # Add GitOps metadata if provided
        if source_repo_url:
            mapping["source_repo_url"] = source_repo_url
        if gitops_repo:
            mapping["gitops_repo"] = gitops_repo
        if gitops_repo_url:
            mapping["gitops_repo_url"] = gitops_repo_url
        if gitops_config_path:
            mapping["gitops_config_path"] = gitops_config_path
        
        await self.redis.hset(key, mapping=mapping)
    
    async def update_service_discovery(
        self,
        name: str,
        version: str,
        source_repo_url: Optional[str] = None,
        gitops_repo: Optional[str] = None,
        gitops_repo_url: Optional[str] = None,
        gitops_config_path: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> None:
        """Update service discovery metadata WITHOUT overwriting metrics.
        
        Used by the K8s observer's annotation discovery cycle. Only writes
        version, repo URLs, and config path. Leaves cpu/memory/error_rate
        untouched so the metrics poll values are never clobbered.
        """
        key = f"darwin:service:{name}"
        mapping: dict[str, str] = {
            "version": version,
            "last_seen": str(time.time()),
        }
        if source_repo_url:
            mapping["source_repo_url"] = source_repo_url
        if gitops_repo:
            mapping["gitops_repo"] = gitops_repo
        if gitops_repo_url:
            mapping["gitops_repo_url"] = gitops_repo_url
        if gitops_config_path:
            mapping["gitops_config_path"] = gitops_config_path
        if icon:
            mapping["icon"] = icon
        
        await self.redis.hset(key, mapping=mapping)

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
            source_repo_url=data.get("source_repo_url"),
            gitops_repo=data.get("gitops_repo"),
            gitops_repo_url=data.get("gitops_repo_url"),
            gitops_config_path=data.get("gitops_config_path"),
            replicas_ready=int(data["replicas_ready"]) if data.get("replicas_ready") else None,
            replicas_desired=int(data["replicas_desired"]) if data.get("replicas_desired") else None,
            escalation_flag=data.get("escalation_flag"),
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
    # Escalation Flag (Service-level suppression)
    # =========================================================================

    async def get_escalation_flag(self, service: str) -> Optional[str]:
        """Targeted HGET for escalation flag — cheaper than full get_service()."""
        return await self.redis.hget(f"darwin:service:{service}", "escalation_flag")

    async def set_escalation_flag(self, service: str, event_id: str, reason: str) -> None:
        """Set escalation suppression flag on a service HASH."""
        safe_reason = reason.replace('\n', ' ').replace('\r', '').replace('|', '-')[:100]
        value = f"{event_id}|{safe_reason}"
        await self.redis.hset(f"darwin:service:{service}", "escalation_flag", value)
        logger.info(f"Escalation flag SET for {service}: {event_id}")

    async def clear_escalation_flag(
        self, service: str, expected_event_id: str | None = None,
    ) -> int:
        """Clear escalation flag. Atomic compare-and-delete when expected_event_id given."""
        key = f"darwin:service:{service}"
        if expected_event_id:
            result = await self._clear_escalation_script(
                keys=[key], args=[expected_event_id],
            )
        else:
            result = await self.redis.hdel(key, "escalation_flag")
        logger.info(
            f"Escalation flag CLEAR for {service}: "
            f"expected={expected_event_id}, result={result}"
        )
        return int(result)

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
                # No data in the last 30s. Fall back to latest entry, but only
                # if it's within the zombie threshold (90s). Beyond that, stale
                # ZSET data creates a visual inconsistency: graph shows "CPU:2%"
                # but health is "unknown" (gray) because last_seen is stale.
                fallback = await self.redis.zrevrange(key, 0, 0, withscores=True)
                if fallback:
                    entry_ts = fallback[0][1]  # score = timestamp
                    if (now - entry_ts) <= 90:  # Within zombie threshold
                        parts = fallback[0][0].split(":")
                        metrics[metric_name] = float(parts[1]) if len(parts) >= 2 else 0.0
                    else:
                        metrics[metric_name] = 0.0  # Stale data -- don't mislead the graph
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
        limit: int = 200,
    ) -> List[ArchitectureEvent]:
        """Get most recent events within time range (newest first)."""
        start = start_time if start_time else 0
        end = end_time if end_time else time.time()
        
        results = await self.redis.zrevrangebyscore(
            "darwin:events", end, start, start=0, num=limit,
        )
        
        events = []
        for event_json in results:
            try:
                data = json.loads(event_json)
                events.append(ArchitectureEvent(**data))
            except Exception as e:
                logger.debug(f"Skipping malformed architecture event: {e}")
        
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
    
    async def get_events_for_service(
        self,
        service: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 200,
    ) -> List[ArchitectureEvent]:
        """Get events filtered by service name in details."""
        all_events = await self.get_events_in_range(start_time, end_time, limit=limit * 5)
        return [
            e for e in all_events 
            if e.details.get("service") == service
        ][:limit]
    
    # =========================================================================
    # Snapshot (Context for Architect)
    # =========================================================================
    
    async def get_snapshot(self) -> Snapshot:
        """
        Get complete Blackboard snapshot for Architect context.
        
        Combines topology and service metadata for AI reasoning.
        """
        topology = await self.get_topology()
        services = await self.get_all_services()
        
        return Snapshot(
            topology=topology,
            services=services,
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
    # Telemetry Processing (DEPRECATED -- no active callers)
    # =========================================================================
    
    async def process_telemetry(self, payload: TelemetryPayload) -> None:
        """
        DEPRECATED: Process incoming telemetry and update all layers.
        
        Previously called by Aligner.process_telemetry() which was removed.
        DarwinClient telemetry push is deprecated in favor of K8s Observer
        annotations (darwin.io/*). Kept for reference -- contains IP registration,
        topology edge creation, and metadata update logic that may be reused.
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
            gitops_config_path=payload.gitops.helm_path if payload.gitops else None,
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
    EVENT_WAITING_APPROVAL = "darwin:event:waiting_approval"
    EVENT_CLOSED = "darwin:event:closed"
    # AGENT_NOTIFY_PREFIX removed -- WebSocket replaces Redis agent notifications

    # Ops journal -- per-service temporal memory for pattern recognition
    JOURNAL_PREFIX = "darwin:journal:"
    JOURNAL_MAX_ENTRIES = 100

    # Slack thread_ts <-> event_id reverse index
    SLACK_THREAD_PREFIX = "darwin:slack:thread:"

    async def create_event(
        self,
        source: str,
        service: str,
        reason: str,
        evidence: "str | EventEvidence",
        subject_type: str = "service",
        created_by_email: Optional[str] = None,
        slack_channel_id: Optional[str] = None,
        slack_thread_ts: Optional[str] = None,
        slack_user_id: Optional[str] = None,
    ) -> str:
        """Create a new event and add to the queue for Brain triage.

        Evidence contract: callers MUST pass a structured EventEvidence object.
        Plain strings are accepted only for backward compat (_coerce_evidence).

        Source patterns:
          aligner    -- source_type="aligner", LLM domain/severity, EventMetrics
          chat/slack -- source_type="chat"/"slack", domain="complicated", severity="info"
          headhunter -- source_type="headhunter", domain="complicated", severity="info"
        """
        from datetime import datetime, timezone
        event = EventDocument(
            source=source,
            service=service,
            subject_type=subject_type,
            brain_phase="triage",
            event=EventInput(
                reason=reason,
                evidence=evidence,
                timeDate=datetime.now(timezone.utc).isoformat(),
            ),
            queued_at=time.time(),
            created_by_email=created_by_email,
            slack_channel_id=slack_channel_id,
            slack_thread_ts=slack_thread_ts,
            slack_user_id=slack_user_id,
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
    ) -> int:
        """Append a conversation turn to an event document.

        Assigns ``turn.turn`` atomically inside WATCH/MULTI from the
        current conversation length.  Returns the assigned turn number,
        or 0 if the event no longer exists (fail-closed).
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for append_turn")
                        return 0
                    event = EventDocument(**json.loads(data))
                    turn.turn = len(event.conversation) + 1
                    event.conversation.append(turn)
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Appended turn {turn.turn} ({turn.actor}.{turn.action}) to event {event_id}")
        return turn.turn

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

    async def update_turn_evidence(
        self,
        event_id: str,
        turn_num: int,
        evidence: str,
    ) -> bool:
        """Update a single turn's evidence by turn number (WATCH/MULTI/EXEC).

        Used by Aligner last-write-wins: update pending confirm evidence in-place.
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
                        if t.turn == turn_num:
                            t.evidence = evidence
                            found = True
                            break
                    if not found:
                        return False
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    logger.debug(f"Updated turn {turn_num} evidence for event {event_id}")
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

    async def defer_event_status(
        self, event_id: str, defer_until: float, delay: int,
    ) -> bool:
        """Atomically set event status to DEFERRED and store defer_until timestamp.

        Uses WATCH/MULTI/EXEC for optimistic locking (same pattern as
        transition_event_status). Also sets the defer_until key with TTL.
        Returns True if the event was found and updated.

        while True (no retry cap): caller appends a "defer" turn BEFORE calling
        this method, so failure would leave conversation/state divergent.
        WatchError means concurrent modification — self-resolves on next iteration.
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
                    event.status = EventStatus.DEFERRED
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    pipe.set(
                        f"{key}:defer_until",
                        str(defer_until),
                        ex=delay + 60,
                    )
                    await pipe.execute()
                    return True
                except WatchError:
                    continue

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

    async def get_active_events_with_status(self) -> dict[str, str]:
        """Get all active event IDs with their current status.

        Returns dict[event_id, status_string]. Uses pipeline for efficiency.
        Covers all IDs in the EVENT_ACTIVE set (new, active, deferred).
        """
        members = list(await self.redis.smembers(self.EVENT_ACTIVE))
        if not members:
            return {}
        pipe = self.redis.pipeline(transaction=False)
        for eid in members:
            pipe.get(f"{self.EVENT_PREFIX}{eid}")
        results = await pipe.execute()
        status_map: dict[str, str] = {}
        for eid, raw in zip(members, results):
            if not raw:
                continue
            try:
                data = json.loads(raw)
                status_map[eid] = data.get("status", "active")
            except (json.JSONDecodeError, TypeError):
                continue
        return status_map

    async def find_active_event_by_source(self, source: str) -> str | None:
        """Find an active event by source. Returns event_id or None."""
        for eid in await self.redis.smembers(self.EVENT_ACTIVE):
            data = await self.redis.get(f"{self.EVENT_PREFIX}{eid}")
            if data:
                try:
                    event = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    continue
                if event.get("source") == source:
                    return eid
        return None

    async def get_flow_metrics(self) -> dict:
        """Flow observability: queue depth + active + waiting_approval. All O(1) Redis ops."""
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.llen(self.EVENT_QUEUE)
            pipe.scard(self.EVENT_ACTIVE)
            pipe.scard(self.EVENT_WAITING_APPROVAL)
            queue_depth, active_count, waiting_approval = await pipe.execute()
        return {
            "queue_depth": queue_depth,
            "active_events": active_count,
            "waiting_approval_events": waiting_approval,
        }

    # =========================================================================
    # Flow History (time-series snapshots for /flow/history)
    # =========================================================================
    FLOW_HISTORY_KEY = "darwin:flow:history"
    FLOW_RETENTION_SECONDS = 604800  # 7 days
    FLOW_DOWNSAMPLE_THRESHOLD = 86400  # 24h — aggregate beyond this

    async def persist_flow_snapshot(self, snapshot: "FlowSnapshot") -> None:
        """Persist a flow snapshot to the time-series sorted set (pipelined)."""
        from ..models import FlowSnapshot  # noqa: F811
        member = json.dumps(snapshot.model_dump(), sort_keys=True, separators=(",", ":"))
        cutoff = snapshot.timestamp - self.FLOW_RETENTION_SECONDS
        async with self.redis.pipeline(transaction=False) as pipe:
            pipe.zadd(self.FLOW_HISTORY_KEY, {member: snapshot.timestamp})
            pipe.zremrangebyscore(self.FLOW_HISTORY_KEY, "-inf", cutoff)
            await pipe.execute()

    _FLOW_MAX_RAW_ENTRIES = 1500

    async def get_flow_history(
        self, range_seconds: int = 3600, downsample: bool = True
    ) -> "list[FlowSnapshot]":
        """Retrieve flow history with optional downsampling for large ranges."""
        from ..models import FlowSnapshot
        now = time.time()
        start = now - min(max(0, range_seconds), self.FLOW_RETENTION_SECONDS)
        results = await self.redis.zrangebyscore(
            self.FLOW_HISTORY_KEY, start, now,
            start=0, num=self._FLOW_MAX_RAW_ENTRIES,
        )
        snapshots: list[FlowSnapshot] = []
        for r in results:
            try:
                snapshots.append(FlowSnapshot(**json.loads(r)))
            except Exception as exc:
                logger.warning("FlowHistory: skipping corrupt entry: %s", exc)
        if downsample and range_seconds > self.FLOW_DOWNSAMPLE_THRESHOLD and len(snapshots) > 300:
            return self._downsample_snapshots(snapshots, bucket_seconds=300)
        return snapshots

    async def get_latest_flow_snapshot(self) -> "FlowSnapshot | None":
        """Read the most recent snapshot (O(1) for /flow enrichment)."""
        from ..models import FlowSnapshot
        results = await self.redis.zrevrangebyscore(
            self.FLOW_HISTORY_KEY, "+inf", "-inf", start=0, num=1
        )
        if results:
            try:
                return FlowSnapshot(**json.loads(results[0]))
            except Exception:
                return None
        return None

    def _downsample_snapshots(
        self, snapshots: "list[FlowSnapshot]", bucket_seconds: int = 300
    ) -> "list[FlowSnapshot]":
        """Aggregate snapshots into time buckets (5-min averages)."""
        if not snapshots:
            return []
        from ..models import FlowSnapshot
        buckets: dict[int, list] = {}
        for s in snapshots:
            bucket_key = int(s.timestamp // bucket_seconds) * bucket_seconds
            buckets.setdefault(bucket_key, []).append(s)
        result: list[FlowSnapshot] = []
        for ts, group in sorted(buckets.items()):
            n = len(group)
            result.append(FlowSnapshot(
                timestamp=float(ts),
                queue_depth=round(sum(s.queue_depth for s in group) / n),
                active_events=round(sum(s.active_events for s in group) / n),
                deferred_events=round(sum(s.deferred_events for s in group) / n),
                busy_agents=round(sum(s.busy_agents for s in group) / n),
                idle_agents=round(sum(s.idle_agents for s in group) / n),
                active_subscriptions=round(sum(s.active_subscriptions for s in group) / n),
                avg_event_age_sec=sum(s.avg_event_age_sec for s in group) / n,
                avg_reconcile_ms=sum(s.avg_reconcile_ms for s in group) / n,
                reconcile_count_delta=sum(s.reconcile_count_delta for s in group),
                error_count_delta=sum(s.error_count_delta for s in group),
                dispatch_total=max(s.dispatch_total for s in group),
                dispatch_success_rate_pct=sum(s.dispatch_success_rate_pct for s in group) / n,
                dispatch_infra_fails=max(s.dispatch_infra_fails for s in group),
                dispatch_circuit_breaks=max(s.dispatch_circuit_breaks for s in group),
                avg_spawn_latency_sec=sum(s.avg_spawn_latency_sec for s in group) / n,
            ))
        return result

    _event_fields: set[str] = set(EventDocument.model_fields.keys())

    async def stamp_event(self, event_id: str, **fields) -> None:
        """Atomically set fields on an event document (WATCH/MULTI/EXEC).

        Used for mid-lifecycle value stream timestamps that cannot be set inline
        at creation or closure. append_turn() loads a fresh event copy, so
        in-memory mutations on event objects in brain.py are NOT persisted by it.
        """
        invalid = set(fields) - self._event_fields
        if invalid:
            logger.warning(f"stamp_event: unknown fields {invalid} for event {event_id}, skipping")
            return
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        return
                    event = EventDocument(**json.loads(data))
                    for field, value in fields.items():
                        setattr(event, field, value)
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue

    MIN_DEFER_DELAY = 30  # seconds -- matches brain.py clamp floor

    async def resolve_defer_timestamps(
        self,
        event_id: str,
        event: "EventDocument",
    ) -> tuple[float | None, float | None]:
        """Return (defer_until, defer_started_at) for a deferred event.

        Reads defer_until from the Redis side key and defer_started_at from the
        last brain.defer conversation turn.  Clamps started > until to avoid
        negative-width countdown bars.
        """
        defer_until: float | None = None
        defer_started_at: float | None = None
        raw = await self.redis.get(f"{self.EVENT_PREFIX}{event_id}:defer_until")
        if raw:
            try:
                defer_until = float(raw)
            except (TypeError, ValueError):
                pass
        for turn in reversed(event.conversation):
            if turn.actor == "brain" and turn.action == "defer":
                defer_started_at = turn.timestamp
                break
        if defer_until is not None and defer_started_at is not None:
            if defer_started_at > defer_until:
                defer_started_at = max(defer_until - float(self.MIN_DEFER_DELAY), 0.0)
        return defer_until, defer_started_at

    async def _get_ticket_nodes(self) -> list[TicketNode]:
        """Batch-load active general/headhunter events as ticket nodes.

        Uses redis.mget() for O(1) roundtrips regardless of event count.
        Shared by get_graph_data() and generate_mermaid().
        """
        event_ids = await self.get_active_events()
        if not event_ids:
            return []

        keys = [f"{self.EVENT_PREFIX}{eid}" for eid in event_ids]
        raw_values = await self.redis.mget(keys)

        tickets: list[TicketNode] = []
        now = time.time()

        for eid, raw in zip(event_ids, raw_values):
            if not raw:
                continue
            event = EventDocument(**json.loads(raw))

            if (event.service != "general"
                    and event.source != "headhunter"
                    and getattr(event, "subject_type", "service") != "kargo_stage"):
                continue

            # Elapsed time from event creation
            try:
                created = datetime.fromisoformat(event.event.timeDate).timestamp()
                elapsed = now - created
            except (ValueError, AttributeError):
                elapsed = 0.0

            # Current agent: last route turn's selectedAgents[0]
            current_agent: str | None = None
            defer_count = 0
            for turn in reversed(event.conversation):
                if current_agent is None and turn.action == "route" and turn.selectedAgents:
                    current_agent = turn.selectedAgents[0]
                if turn.action == "defer":
                    defer_count += 1

            has_plan = any(t.action == "plan" for t in event.conversation)
            if not has_plan:
                has_plan = event.event.reason.lstrip().startswith("---")
            if not has_plan and isinstance(event.event.evidence, EventEvidence):
                has_plan = event.event.evidence.source_type == "headhunter"

            # PROBE: log Brain think-turn evidence for resolved_service heuristic discovery
            if logger.isEnabledFor(logging.DEBUG):
                for turn in event.conversation:
                    if turn.actor == "brain" and turn.action == "triage" and turn.thoughts:
                        logger.debug(
                            f"[resolved_service probe] event={eid} "
                            f"actor={turn.actor} action={turn.action} "
                            f"thoughts={turn.thoughts[:120]}"
                        )

            defer_until, defer_started_at = await self.resolve_defer_timestamps(
                eid, event,
            ) if event.status.value == "deferred" else (None, None)

            tickets.append(TicketNode(
                event_id=eid,
                status=event.status.value,
                source=event.source,
                reason=event.event.reason[:80],
                turn_count=len(event.conversation),
                elapsed_seconds=round(elapsed, 1),
                current_agent=current_agent,
                defer_count=defer_count,
                defer_until=defer_until,
                defer_started_at=defer_started_at,
                has_work_plan=has_plan,
            ))

        return tickets

    async def get_closed_event_ids(self, limit: int = 500) -> list[str]:
        """Get closed event IDs from the ZSET (most recent first, capped)."""
        return await self.redis.zrevrange(self.EVENT_CLOSED, 0, limit - 1)

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

    async def get_recent_closed_by_source(
        self, source: str, minutes: int = 30
    ) -> list[EventDocument]:
        """Get recently closed events filtered by source (e.g., 'headhunter').

        Uses pipeline for batch-GET. Scoped to source to keep the result set small.
        """
        cutoff = time.time() - (minutes * 60)
        event_ids = await self.redis.zrangebyscore(self.EVENT_CLOSED, cutoff, "+inf")
        if not event_ids:
            return []
        async with self.redis.pipeline(transaction=False) as pipe:
            for eid in event_ids:
                pipe.get(f"{self.EVENT_PREFIX}{eid}")
            docs = await pipe.execute()
        results = []
        for raw in docs:
            if not raw:
                continue
            event = EventDocument(**json.loads(raw))
            if event.source == source:
                results.append(event)
        return results

    async def is_feedback_sent(self, event_id: str) -> bool:
        """Check if headhunter feedback was already sent for an event."""
        return bool(await self.redis.get(f"darwin:headhunter:feedback:{event_id}"))

    async def mark_feedback_sent(self, event_id: str, ttl: int = 172800) -> None:
        """Mark headhunter feedback as sent (48h TTL covers 24h scan window + margin)."""
        await self.redis.set(f"darwin:headhunter:feedback:{event_id}", "1", ex=ttl)

    async def append_journal(self, service: str, entry: str) -> None:
        """Append a one-line ops journal entry for a service."""
        from datetime import datetime, timezone
        key = f"{self.JOURNAL_PREFIX}{service}"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        await self.redis.rpush(key, f"[{timestamp}] {entry}")
        await self.redis.ltrim(key, -self.JOURNAL_MAX_ENTRIES, -1)

    async def get_journal(self, service: str) -> list[str]:
        """Get all ops journal entries for a service (newest last)."""
        key = f"{self.JOURNAL_PREFIX}{service}"
        return await self.redis.lrange(key, 0, -1)

    async def get_recent_journal_entries(self, limit: int = 30, per_service: int = 3) -> list[str]:
        """Get recent journal entries across ALL services, sorted by timestamp descending."""
        from datetime import datetime as _dt
        entries: list[tuple[_dt, str, str]] = []
        async for key in self.redis.scan_iter(match=f"{self.JOURNAL_PREFIX}*"):
            service = key.removeprefix(self.JOURNAL_PREFIX) if isinstance(key, str) else key.decode().removeprefix(self.JOURNAL_PREFIX)
            raw = await self.redis.lrange(key, -per_service, -1)
            for entry in raw:
                entry_str = entry if isinstance(entry, str) else entry.decode()
                try:
                    ts_str = entry_str.split("]")[0].lstrip("[")
                    ts = _dt.strptime(ts_str, "%Y-%m-%d %H:%M")
                except (ValueError, IndexError):
                    ts = _dt.min
                entries.append((ts, service, entry_str))
        entries.sort(key=lambda x: x[0], reverse=True)
        return [f"[{svc}] {text}" for _, svc, text in entries[:limit]]

    async def close_event(self, event_id: str, summary: str, close_reason: str = "resolved") -> None:
        """Close an event with summary. Move from active to closed.

        close_reason: structured reason for closure. Stored in close turn's evidence field.
        Values: resolved, stale, timeout, force_closed, duplicate, user_closed, error.
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
                    event.closed_at = time.time()
                    event.status = EventStatus.CLOSED
                    close_turn = ConversationTurn(
                        turn=len(event.conversation) + 1,
                        actor="brain",
                        action="close",
                        thoughts=summary,
                        evidence=close_reason,
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

    # =========================================================================
    # Approval Parking (park/resume for events awaiting human authorization)
    # =========================================================================

    async def park_for_approval(self, event_id: str) -> None:
        """Move event from active to waiting_approval set + update status atomically."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"park_for_approval: {event_id} not found")
                        return
                    event = EventDocument(**json.loads(data))
                    if event.status == EventStatus.WAITING_APPROVAL:
                        return  # Already parked, idempotent
                    event.status = EventStatus.WAITING_APPROVAL
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    pipe.srem(self.EVENT_ACTIVE, event_id)
                    pipe.sadd(self.EVENT_WAITING_APPROVAL, event_id)
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.info(f"Parked event for approval: {event_id}")

    async def resume_from_approval(self, event_id: str) -> None:
        """Move event from waiting_approval back to active set + update status atomically."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"resume_from_approval: {event_id} not found")
                        return
                    event = EventDocument(**json.loads(data))
                    event.status = EventStatus.ACTIVE
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    pipe.srem(self.EVENT_WAITING_APPROVAL, event_id)
                    pipe.sadd(self.EVENT_ACTIVE, event_id)
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.info(f"Resumed event from approval: {event_id}")

    async def get_waiting_approval_events(self) -> list[str]:
        """Return all event IDs in the waiting_approval set."""
        return [eid.decode() if isinstance(eid, bytes) else eid
                for eid in await self.redis.smembers(self.EVENT_WAITING_APPROVAL)]

    # =========================================================================
    # Slack Thread Mapping (reverse index for DM thread replies)
    # =========================================================================

    async def update_event_slack_context(
        self, event_id: str, channel_id: str, thread_ts: str, user_id: str = "",
    ) -> None:
        """Set Slack correlation fields on an EventDocument (WATCH/MULTI)."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for slack context update")
                        return
                    event = EventDocument(**json.loads(data))
                    event.slack_channel_id = channel_id
                    event.slack_thread_ts = thread_ts
                    if user_id:
                        event.slack_user_id = user_id
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Slack context set on event {event_id}: ch={channel_id} ts={thread_ts}")

    async def update_event_domain(self, event_id: str, brain_domain: str) -> None:
        """Set Brain's Cynefin classification on an EventDocument (WATCH/MULTI)."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for domain update")
                        return
                    event = EventDocument(**json.loads(data))
                    if isinstance(event.event.evidence, EventEvidence):
                        event.event.evidence.brain_domain = brain_domain
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Brain domain set on event {event_id}: {brain_domain}")

    async def update_event_phase(self, event_id: str, brain_phase: str) -> None:
        """Set Brain's declared processing phase on an EventDocument (WATCH/MULTI)."""
        brain_phase = _resolve_phase(brain_phase)
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for phase update")
                        return
                    event = EventDocument(**json.loads(data))
                    event.brain_phase = brain_phase
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Brain phase set on event {event_id}: {brain_phase}")

    async def update_event_gitlab_context(self, event_id: str, updates: dict) -> None:
        """Patch gitlab_context fields on an active event's evidence (WATCH/MULTI).

        Merges `updates` into the existing gitlab_context dict. Also updates
        evidence.severity if 'severity' key is present in updates (source
        reclassification on refresh -- does NOT touch brain_severity).
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for gitlab_context update")
                        return
                    event = EventDocument(**json.loads(data))
                    if isinstance(event.event.evidence, EventEvidence):
                        if event.event.evidence.github_context is not None:
                            logger.warning(f"Rejecting gitlab_context update on event {event_id}: github_context already set")
                            return
                        gl = event.event.evidence.gitlab_context or {}
                        gl.update(updates)
                        event.event.evidence.gitlab_context = gl
                        if "severity" in updates:
                            event.event.evidence.severity = updates["severity"]
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"GitLab context updated on event {event_id}: {list(updates.keys())}")

    async def update_event_github_context(self, event_id: str, updates: dict) -> None:
        """Patch github_context fields on an active event's evidence (WATCH/MULTI).

        Merges `updates` into the existing github_context dict. Also updates
        evidence.severity if 'severity' key is present in updates.
        Rejects if gitlab_context already exists (one-of invariant).
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for github_context update")
                        return
                    event = EventDocument(**json.loads(data))
                    if isinstance(event.event.evidence, EventEvidence):
                        if event.event.evidence.gitlab_context is not None:
                            logger.warning(f"Rejecting github_context update on event {event_id}: gitlab_context already set")
                            return
                        gc = event.event.evidence.github_context or {}
                        gc.update(updates)
                        event.event.evidence.github_context = gc
                        if "severity" in updates:
                            event.event.evidence.severity = updates["severity"]
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"GitHub context updated on event {event_id}: {list(updates.keys())}")

    async def update_event_kargo_context(self, event_id: str, updates: dict) -> None:
        """Patch kargo_context fields on an active event's evidence (WATCH/MULTI).

        Merges `updates` into the existing kargo_context dict. Used by
        refresh_kargo_context to update mr_url when a re-promotion creates a new MR.
        """
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for kargo_context update")
                        return
                    event = EventDocument(**json.loads(data))
                    if isinstance(event.event.evidence, EventEvidence):
                        kc = event.event.evidence.kargo_context or {}
                        kc.update(updates)
                        event.event.evidence.kargo_context = kc
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Kargo context updated on event {event_id}: {list(updates.keys())}")

    async def update_event_severity(self, event_id: str, brain_severity: str) -> None:
        """Set Brain-assessed severity override on event evidence (WATCH/MULTI)."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for severity update")
                        return
                    event = EventDocument(**json.loads(data))
                    if isinstance(event.event.evidence, EventEvidence):
                        event.event.evidence.brain_severity = brain_severity
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Brain severity set on event {event_id}: {brain_severity}")

    async def update_event_sticky_notes(
        self, event_id: str, sticky_notes: list[dict], unread_notes: int,
    ) -> None:
        """Update sticky notes and unread counter on an EventDocument (WATCH/MULTI)."""
        key = f"{self.EVENT_PREFIX}{event_id}"
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(key)
                    data = await pipe.get(key)
                    if not data:
                        logger.warning(f"Event {event_id} not found for sticky_notes update")
                        return
                    event = EventDocument(**json.loads(data))
                    event.sticky_notes = sticky_notes
                    event.unread_notes = unread_notes
                    pipe.multi()
                    pipe.set(key, json.dumps(event.model_dump()))
                    await pipe.execute()
                    break
                except WatchError:
                    continue
        logger.debug(f"Sticky notes updated on event {event_id}: {unread_notes} unread")

    SLACK_MAPPING_TTL = 86400  # 24h safety net (cleaned explicitly on event close)

    async def set_slack_mapping(
        self, channel_id: str, thread_ts: str, event_id: str,
    ) -> None:
        """Map a Slack thread to an event for reverse-lookup by on_dm_message."""
        key = f"{self.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        await self.redis.set(key, event_id, ex=self.SLACK_MAPPING_TTL)
        logger.debug(f"Slack mapping: {channel_id}:{thread_ts} -> {event_id}")

    async def get_event_by_slack_thread(
        self, channel_id: str, thread_ts: str,
    ) -> Optional[str]:
        """Reverse-lookup event_id from a Slack thread_ts. Returns None if not found."""
        key = f"{self.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        return await self.redis.get(key)

    async def delete_slack_mapping(
        self, channel_id: str, thread_ts: str,
    ) -> None:
        """Remove Slack thread mapping on event close (TTL cleanup)."""
        key = f"{self.SLACK_THREAD_PREFIX}{channel_id}:{thread_ts}"
        await self.redis.delete(key)
        logger.debug(f"Slack mapping deleted: {channel_id}:{thread_ts}")

    # =========================================================================
    # Report Persistence (90-day TTL snapshots)
    # =========================================================================

    REPORT_PREFIX = "darwin:report:"
    REPORT_INDEX = "darwin:reports:index"
    REPORT_TTL = 7_776_000  # 90 days in seconds

    async def persist_report(self, event_id: str) -> None:
        """Generate and persist a markdown report for a closed event.

        Fault-tolerant: logs a warning and returns on any failure.
        Must NEVER crash the caller's close flow.
        """
        try:
            event = await self.get_event(event_id)
            if not event:
                logger.warning(f"persist_report: event {event_id} not found in Redis, skipping")
                return

            service_meta = None
            mermaid = ""
            try:
                service_meta = await self.get_service(event.service)
            except Exception:
                pass
            if event.source != "headhunter" and getattr(event, "subject_type", "service") != "kargo_stage":
                try:
                    mermaid = await self.generate_mermaid()
                except Exception:
                    pass

            from ..utils.event_markdown import event_to_markdown
            markdown = event_to_markdown(event, service_meta, mermaid)

            # Add journal context
            journal = await self.get_journal(event.service)
            if journal:
                markdown += "\n\n## Service Ops Journal\n\n"
                for entry in journal:
                    markdown += f"- {entry}\n"

            # Extract evidence metadata
            evidence = event.event.evidence
            domain = "complicated"
            severity = "warning"
            if isinstance(evidence, EventEvidence):
                domain = evidence.brain_domain or evidence.domain
                severity = evidence.brain_severity or evidence.severity

            triggered_by = None
            if isinstance(evidence, EventEvidence) and evidence.triggered_by:
                triggered_by = evidence.triggered_by

            indexed_at = time.time()
            report_data = {
                "event_id": event_id,
                "markdown": markdown,
                "service": event.service,
                "source": event.source,
                "subject_type": getattr(event, "subject_type", "service"),
                "domain": domain,
                "severity": severity,
                "turns": len(event.conversation),
                "reason": event.event.reason,
                "closed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "indexed_at": indexed_at,
                "triggered_by": triggered_by,
            }

            obs_summary = await self.get_observation_summary(event_id)
            if obs_summary:
                report_data["observation_summary"] = obs_summary

            # Cleanup observation keys after summary is captured
            obs_keys: list[str] = []
            async for k in self.redis.scan_iter(
                match=f"{self.OBS_KEY_PREFIX}{event_id}{self.OBS_KEY_INFIX}*", count=100
            ):
                obs_keys.append(k if isinstance(k, str) else k.decode())
            if obs_keys:
                await self.redis.delete(*obs_keys)

            key = f"{self.REPORT_PREFIX}{event_id}"
            await self.redis.set(key, json.dumps(report_data), ex=self.REPORT_TTL)
            await self.redis.zadd(self.REPORT_INDEX, {event_id: indexed_at})
            logger.info(f"Persisted report for event {event_id} (TTL={self.REPORT_TTL}s)")

        except Exception as e:
            logger.warning(f"persist_report failed for {event_id} (non-fatal): {e}")

    async def list_reports(
        self, limit: int = 50, offset: int = 0, service: Optional[str] = None
    ) -> list[dict]:
        """List persisted report metadata, sorted newest first.

        Uses MGET for batch fetching instead of N individual GETs.
        """
        # Fetch all IDs from sorted set (newest first)
        all_ids: list[str] = await self.redis.zrevrangebyscore(
            self.REPORT_INDEX,
            max="+inf",
            min="-inf",
        )
        if not all_ids:
            return []

        # Batch fetch all report keys
        keys = [f"{self.REPORT_PREFIX}{eid}" for eid in all_ids]
        raw_values = await self.redis.mget(keys)

        results: list[dict] = []
        expired_ids: list[str] = []
        for eid, raw in zip(all_ids, raw_values):
            if not raw:
                expired_ids.append(eid)
                continue
            data = json.loads(raw)
            # Optional service filter
            if service and data.get("service") != service:
                continue
            # Strip markdown for list response (metadata only)
            meta = {k: v for k, v in data.items() if k != "markdown"}
            results.append(meta)

        # Clean up expired entries from the index
        if expired_ids:
            await self.redis.zrem(self.REPORT_INDEX, *expired_ids)

        # Apply pagination
        return results[offset : offset + limit]

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
    ) -> dict:
        """Search reports with compound cursor pagination and facet filters.

        Returns {items: list[dict], next_cursor: str|None, has_more: bool}.
        Cursor format: '{score}:{event_id}' for stable keyset pagination.
        """
        max_score = end_time if end_time is not None else "+inf"
        min_score = start_time if start_time is not None else "-inf"

        all_with_scores: list[tuple[str, float]] = await self.redis.zrevrangebyscore(
            self.REPORT_INDEX,
            max=max_score,
            min=min_score,
            withscores=True,
        )
        if not all_with_scores:
            return {"items": [], "next_cursor": None, "has_more": False}

        if len(all_with_scores) > 1000:
            logger.warning(f"search_reports: large ZSET range ({len(all_with_scores)} IDs)")

        cursor_score: Optional[float] = None
        cursor_event_id: Optional[str] = None
        if cursor:
            parts = cursor.split(":", 1)
            if len(parts) == 2:
                cursor_score = float(parts[0])
                cursor_event_id = parts[1]

        keys = [f"{self.REPORT_PREFIX}{eid}" for eid, _ in all_with_scores]
        raw_values = await self.redis.mget(keys)

        results: list[dict] = []
        expired_ids: list[str] = []
        past_cursor = cursor is None

        for (eid, score), raw in zip(all_with_scores, raw_values):
            if not raw:
                expired_ids.append(eid)
                continue

            if not past_cursor:
                if score == cursor_score and eid == cursor_event_id:
                    past_cursor = True
                    continue
                elif score < cursor_score:
                    past_cursor = True
                else:
                    continue

            data = json.loads(raw)
            meta = {k: v for k, v in data.items() if k != "markdown"}
            meta.setdefault("indexed_at", score)

            if service and meta.get("service") != service:
                continue
            if source and meta.get("source") != source:
                continue
            if domain and meta.get("domain") != domain:
                continue
            if severity and meta.get("severity") != severity:
                continue
            if q:
                q_lower = q.lower()
                searchable = f"{meta.get('event_id', '')} {meta.get('service', '')} {meta.get('reason', '')}".lower()
                if q_lower not in searchable:
                    continue

            results.append(meta)

        if expired_ids:
            await self.redis.zrem(self.REPORT_INDEX, *expired_ids)

        has_more = len(results) > limit
        page = results[:limit]

        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = f"{last['indexed_at']}:{last['event_id']}"

        return {"items": page, "next_cursor": next_cursor, "has_more": has_more}

    async def get_report(self, event_id: str) -> Optional[dict]:
        """Get a persisted report by event ID (full content including markdown)."""
        raw = await self.redis.get(f"{self.REPORT_PREFIX}{event_id}")
        if not raw:
            return None
        return json.loads(raw)

    # =========================================================================
    # TimeKeeper (Scheduled Tasks)
    # =========================================================================

    TIMEKEEPER_SCHEDULES = "darwin:timekeeper:schedules"
    TIMEKEEPER_PENDING = "darwin:timekeeper:pending"
    TIMEKEEPER_USER_PREFIX = "darwin:timekeeper:user:"

    async def create_schedule(self, sched) -> str:
        """Persist a ScheduledEvent. HSET + ZADD + SADD user set."""
        key = self.TIMEKEEPER_SCHEDULES
        pending = self.TIMEKEEPER_PENDING
        user_key = f"{self.TIMEKEEPER_USER_PREFIX}{sched.created_by}"

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.watch(key)
            pipe.multi()
            pipe.hset(key, sched.id, sched.model_dump_json())
            if sched.enabled:
                pipe.zadd(pending, {sched.id: sched.fire_at})
            pipe.sadd(user_key, sched.id)
            await pipe.execute()
        return sched.id

    async def get_schedule(self, sched_id: str):
        """Get a single ScheduledEvent by ID."""
        from ..models import ScheduledEvent
        raw = await self.redis.hget(self.TIMEKEEPER_SCHEDULES, sched_id)
        if not raw:
            return None
        return ScheduledEvent.model_validate_json(raw)

    async def list_schedules(self) -> list:
        """List all ScheduledEvents."""
        from ..models import ScheduledEvent
        all_raw = await self.redis.hgetall(self.TIMEKEEPER_SCHEDULES)
        return [ScheduledEvent.model_validate_json(v) for v in all_raw.values()]

    async def update_schedule(self, sched_id: str, updates: dict) -> bool:
        """Update fields on a schedule. Re-ZADD if fire_at changed."""
        raw = await self.redis.hget(self.TIMEKEEPER_SCHEDULES, sched_id)
        if not raw:
            return False
        data = json.loads(raw)
        data.update(updates)

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.watch(self.TIMEKEEPER_SCHEDULES)
            pipe.multi()
            pipe.hset(self.TIMEKEEPER_SCHEDULES, sched_id, json.dumps(data))
            if "fire_at" in updates and data.get("enabled", True):
                pipe.zadd(self.TIMEKEEPER_PENDING, {sched_id: updates["fire_at"]})
            await pipe.execute()
        return True

    async def delete_schedule(self, sched_id: str, created_by: str) -> bool:
        """Delete a schedule. HDEL + ZREM + SREM user set."""
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.watch(self.TIMEKEEPER_SCHEDULES)
            pipe.multi()
            pipe.hdel(self.TIMEKEEPER_SCHEDULES, sched_id)
            pipe.zrem(self.TIMEKEEPER_PENDING, sched_id)
            pipe.srem(f"{self.TIMEKEEPER_USER_PREFIX}{created_by}", sched_id)
            await pipe.execute()
        return True

    async def pop_due_schedule(self):
        """Atomically pop the next due schedule via ZPOPMIN.

        Returns (sched_id, ScheduledEvent) or None if nothing is due.
        """
        import time as _time
        from ..models import ScheduledEvent
        result = await self.redis.zpopmin(self.TIMEKEEPER_PENDING, count=1)
        if not result:
            return None
        sched_id_bytes, score = result[0]
        sched_id = sched_id_bytes if isinstance(sched_id_bytes, str) else sched_id_bytes.decode()
        if score > _time.time():
            await self.redis.zadd(self.TIMEKEEPER_PENDING, {sched_id: score})
            return None
        raw = await self.redis.hget(self.TIMEKEEPER_SCHEDULES, sched_id)
        if not raw:
            return None
        return (sched_id, ScheduledEvent.model_validate_json(raw))

    async def requeue_schedule(self, sched_id: str, score: float) -> None:
        """Re-ZADD a schedule on fire failure (fallback safety net)."""
        await self.redis.zadd(self.TIMEKEEPER_PENDING, {sched_id: score})

    async def advance_schedule(self, sched_id: str, next_fire_at: float) -> None:
        """Update fire_at in HASH and ZADD new score for recurring schedules."""
        import time as _time
        raw = await self.redis.hget(self.TIMEKEEPER_SCHEDULES, sched_id)
        if not raw:
            return
        data = json.loads(raw)
        data["fire_at"] = next_fire_at
        data["last_fired"] = _time.time()

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.watch(self.TIMEKEEPER_SCHEDULES)
            pipe.multi()
            pipe.hset(self.TIMEKEEPER_SCHEDULES, sched_id, json.dumps(data))
            if data.get("enabled", True):
                pipe.zadd(self.TIMEKEEPER_PENDING, {sched_id: next_fire_at})
            await pipe.execute()

    async def toggle_schedule(self, sched_id: str, enabled: bool) -> bool:
        """Enable/disable a schedule. ZREM on pause, ZADD on resume."""
        raw = await self.redis.hget(self.TIMEKEEPER_SCHEDULES, sched_id)
        if not raw:
            return False
        data = json.loads(raw)
        data["enabled"] = enabled

        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.watch(self.TIMEKEEPER_SCHEDULES)
            pipe.multi()
            pipe.hset(self.TIMEKEEPER_SCHEDULES, sched_id, json.dumps(data))
            if enabled:
                pipe.zadd(self.TIMEKEEPER_PENDING, {sched_id: data["fire_at"]})
            else:
                pipe.zrem(self.TIMEKEEPER_PENDING, sched_id)
            await pipe.execute()
        return True

    async def count_user_schedules(self, email: str) -> int:
        """Count active schedules for a user."""
        return await self.redis.scard(f"{self.TIMEKEEPER_USER_PREFIX}{email}")

    # =========================================================================
    # Nightwatcher (Shift Consolidation Staging)
    # =========================================================================

    NIGHTWATCHER_PENDING = "darwin:nightwatcher:pending"
    NIGHTWATCHER_INFLIGHT = "darwin:nightwatcher:inflight"
    SHIFT_PREFIX = "darwin:nightwatcher:shift:"
    SHIFT_INDEX = "darwin:nightwatcher:shifts:index"
    SHIFT_TTL = 2_592_000   # 30 days
    INFLIGHT_TTL = 3_600    # 1h safety net

    async def stage_escalation(self, data) -> None:
        """Stage an escalation for Nightwatcher consolidation. ZADD to pending ZSET."""
        payload = data.model_dump_json()
        await self.redis.zadd(self.NIGHTWATCHER_PENDING, {payload: data.staged_at})
        logger.info("Nightwatcher: staged escalation %s (service=%s)", data.event_id, data.service)

    async def lease_pending_escalations(self, before_ts: float) -> tuple[list, list[str]]:
        """Atomically lease all pending escalations: move from pending ZSET to inflight SET.

        Returns (parsed_escalations, raw_json_members) tuple. The raw JSON strings
        are needed for commit_inflight() and requeue -- the inflight SET stores
        the same JSON strings as the ZSET members.
        """
        import redis.exceptions as _rexc
        from ..models import StagedEscalation

        while True:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(self.NIGHTWATCHER_PENDING)
                    members = await pipe.zrangebyscore(self.NIGHTWATCHER_PENDING, "-inf", before_ts)
                    if not members:
                        await pipe.reset()
                        return [], []
                    json_members = [m if isinstance(m, str) else m.decode() for m in members]
                    pipe.multi()
                    for jm in json_members:
                        pipe.zrem(self.NIGHTWATCHER_PENDING, jm)
                        pipe.sadd(self.NIGHTWATCHER_INFLIGHT, jm)
                    pipe.expire(self.NIGHTWATCHER_INFLIGHT, self.INFLIGHT_TTL)
                    await pipe.execute()
                    break
            except _rexc.WatchError:
                logger.info("Nightwatcher: lease WatchError, retrying")
                continue

        escalations = [StagedEscalation.model_validate_json(jm) for jm in json_members]
        logger.info("Nightwatcher: leased %d escalations (inflight TTL=%ds)", len(escalations), self.INFLIGHT_TTL)
        return escalations, json_members

    async def commit_inflight(self, json_members: list[str]) -> None:
        """Remove committed items from inflight SET after successful persist."""
        if not json_members:
            return
        await self.redis.srem(self.NIGHTWATCHER_INFLIGHT, *json_members)
        logger.info("Nightwatcher: committed %d inflight items", len(json_members))

    async def requeue_inflight(self) -> int:
        """On startup: recover inflight items from a prior crash back to pending.

        Reads all members from inflight SET, re-ZADDs to pending with
        original staged_at timestamps, then DELetes the inflight SET.
        Returns the number of requeued items.
        """
        import json as _json
        members = await self.redis.smembers(self.NIGHTWATCHER_INFLIGHT)
        if not members:
            return 0
        json_members = [m if isinstance(m, str) else m.decode() for m in members]
        mapping: dict[str, float] = {}
        for jm in json_members:
            try:
                data = _json.loads(jm)
                mapping[jm] = data.get("staged_at", 0.0)
            except Exception:
                logger.warning("Nightwatcher: skipping corrupt inflight member: %s", jm[:100])
        if mapping:
            await self.redis.zadd(self.NIGHTWATCHER_PENDING, mapping)
        await self.redis.delete(self.NIGHTWATCHER_INFLIGHT)
        logger.warning("Nightwatcher: requeued %d inflight items from prior crash", len(mapping))
        return len(mapping)

    async def count_pending_escalations(self) -> int:
        """Count pending escalations waiting for next sweep."""
        return await self.redis.zcard(self.NIGHTWATCHER_PENDING)

    async def restage_orphans(self, json_members: list[str]) -> int:
        """Re-stage orphan escalations back to pending ZSET for next sweep."""
        import json as _json
        count = 0
        for jm in json_members:
            try:
                data = _json.loads(jm)
                await self.redis.zadd(self.NIGHTWATCHER_PENDING, {jm: data.get("staged_at", 0.0)})
                count += 1
            except Exception:
                logger.warning("Nightwatcher: corrupt orphan skipped: %s", jm[:100])
        if count:
            logger.warning("Nightwatcher: restaged %d orphan escalations", count)
        return count

    async def persist_shift_report(self, report) -> None:
        """Persist a ShiftReport for the Shifts UI. SET + ZADD index."""
        key = f"{self.SHIFT_PREFIX}{report.shift_date}:{report.window}"
        await self.redis.set(key, report.model_dump_json(), ex=self.SHIFT_TTL)
        await self.redis.zadd(self.SHIFT_INDEX, {f"{report.shift_date}:{report.window}": report.started_at or time.time()})
        logger.info("Nightwatcher: persisted shift report %s:%s (status=%s)", report.shift_date, report.window, report.status)

    async def get_shift_report(self, date: str, window: str):
        """Get a persisted ShiftReport by date and window."""
        from ..models import ShiftReport
        raw = await self.redis.get(f"{self.SHIFT_PREFIX}{date}:{window}")
        if not raw:
            return None
        return ShiftReport.model_validate_json(raw)

    async def list_shift_reports(self, from_ts: float, to_ts: float) -> list[dict]:
        """List shift report metadata for a time range. ZRANGEBYSCORE + MGET."""
        import json as _json
        keys = await self.redis.zrangebyscore(self.SHIFT_INDEX, from_ts, to_ts)
        if not keys:
            return []
        decoded = [k if isinstance(k, str) else k.decode() for k in keys]
        full_keys = [f"{self.SHIFT_PREFIX}{k}" for k in decoded]
        raw_reports = await self.redis.mget(full_keys)
        results = []
        for raw in raw_reports:
            if not raw:
                continue
            data = _json.loads(raw)
            results.append({
                "shift_date": data.get("shift_date", ""),
                "window": data.get("window", ""),
                "status": data.get("status", ""),
                "escalation_count": len(data.get("manifest", [])),
                "incident_count": len(data.get("incidents", [])),
                "noise_reduction_pct": data.get("metrics", {}).get("noise_reduction_pct", 0),
            })
        results.sort(key=lambda r: r["shift_date"], reverse=True)
        return results

    # =========================================================================
    # Observations (FRIDAY numeric series -- event-scoped + global timeline)
    # =========================================================================
    # Event key:  darwin:event:{id}:obs:{name}  ZSET (archive, cleaned on close)
    # Global key: darwin:obs:{name}             ZSET (7-day rolling window)
    # Index key:  darwin:obs:_index             SET  (all observation names)
    # Member format (both): {iso}:{value}:{unit}:{phase}:{event_id}:{service}
    # ZADD is atomic; no WATCH needed.

    OBS_KEY_PREFIX = "darwin:event:"
    OBS_KEY_INFIX = ":obs:"
    OBS_GLOBAL_PREFIX = "darwin:obs:"
    OBS_INDEX_KEY = "darwin:obs:_index"
    OBS_RETENTION_SECONDS = 604800  # 7 days

    async def record_observation(
        self, event_id: str, name: str, value: float, unit: str, brain_phase: str = "",
    ) -> dict:
        """Record a numeric observation to both event-scoped and global timelines.

        If brain_phase is empty, derives it from the event document (single GET).
        """
        now = time.time()
        event = await self.get_event(event_id)
        if not brain_phase and event:
            brain_phase = _resolve_phase(event.brain_phase)

        service = ""
        if event:
            service = getattr(event, "service", "") or ""

        iso = datetime.utcfromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%SZ")
        member = f"{iso}:{value}:{unit}:{brain_phase}:{event_id}:{service}"

        event_key = f"{self.OBS_KEY_PREFIX}{event_id}{self.OBS_KEY_INFIX}{name}"
        global_key = f"{self.OBS_GLOBAL_PREFIX}{name}"

        pipe = self.redis.pipeline(transaction=False)
        pipe.zadd(event_key, {member: now})
        pipe.zadd(global_key, {member: now})
        pipe.sadd(self.OBS_INDEX_KEY, name)
        pipe.zremrangebyscore(global_key, "-inf", now - self.OBS_RETENTION_SECONDS)
        results = await pipe.execute()
        count = await self.redis.zcard(event_key)

        event_opened = ""
        event_age_minutes = 0.0
        if event and event.event:
            created = event.event.timeDate
            if created:
                event_opened = created
                try:
                    from datetime import datetime as _dt
                    opened_ts = _dt.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                    event_age_minutes = round((now - opened_ts) / 60, 1)
                except (ValueError, TypeError, AttributeError):
                    pass

        return {
            "recorded": True,
            "name": name,
            "value": value,
            "unit": unit or "",
            "count": count,
            "recorded_at": iso,
            "event_age_minutes": event_age_minutes,
        }

    async def list_observations(
        self,
        event_id: str | None = None,
        service: str | None = None,
        name: str | None = None,
    ) -> dict:
        """List observation series with temporal stats.

        Modes:
        - event_id set: read event-scoped keys (existing behaviour for archive/drill-down)
        - event_id None: read global timeline (darwin:obs:{name}), 7-day window
        Filters: service, name narrow the results post-read.
        """
        now = time.time()

        if event_id:
            keys_map = await self._obs_keys_for_event(event_id, name)
        else:
            keys_map = await self._obs_keys_global(name)

        event_opened = ""
        event_age_minutes = 0.0
        if event_id:
            event = await self.get_event(event_id)
            if event and event.event:
                created = event.event.timeDate
                if created:
                    event_opened = created
                    try:
                        from datetime import datetime as _dt
                        opened_ts = _dt.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                        event_age_minutes = round((now - opened_ts) / 60, 1)
                    except (ValueError, TypeError, AttributeError):
                        pass

        cutoff = now - self.OBS_RETENTION_SECONDS if not event_id else 0
        series_list = []
        for obs_name, redis_key in sorted(keys_map.items()):
            min_score = cutoff if cutoff else "-inf"
            members = await self.redis.zrangebyscore(redis_key, min_score, "+inf", withscores=True)
            if not members:
                continue

            points = []
            for raw_member, score in members:
                m = raw_member if isinstance(raw_member, str) else raw_member.decode()
                pt = self._parse_obs_member(m, score)
                if service and pt.get("service", "") != service:
                    continue
                if event_id and not pt.get("event_id"):
                    pt["event_id"] = event_id
                points.append(pt)

            if not points:
                continue

            values = [p["value"] for p in points]
            first_at = points[0]["timestamp"]
            last_at = points[-1]["timestamp"]
            span_minutes = round((points[-1]["epoch"] - points[0]["epoch"]) / 60, 1) if len(points) > 1 else 0.0

            trend = "stable"
            if len(values) >= 2:
                first_half = sum(values[:len(values) // 2]) / max(len(values) // 2, 1)
                second_half = sum(values[len(values) // 2:]) / max(len(values) - len(values) // 2, 1)
                if second_half > first_half * 1.1:
                    trend = "rising"
                elif second_half < first_half * 0.9:
                    trend = "falling"

            series_list.append({
                "name": obs_name,
                "count": len(points),
                "min": min(values),
                "max": max(values),
                "latest_value": values[-1],
                "unit": points[-1]["unit"],
                "first_at": first_at,
                "last_at": last_at,
                "span_minutes": span_minutes,
                "trend": trend,
                "points": points,
            })

        return {
            "event_id": event_id or "",
            "event_opened": event_opened,
            "event_age_minutes": event_age_minutes,
            "observations": series_list,
        }

    async def _obs_keys_for_event(self, event_id: str, name: str | None = None) -> dict[str, str]:
        """Return {obs_name: redis_key} for event-scoped observation keys."""
        if name:
            key = f"{self.OBS_KEY_PREFIX}{event_id}{self.OBS_KEY_INFIX}{name}"
            return {name: key}
        pattern = f"{self.OBS_KEY_PREFIX}{event_id}{self.OBS_KEY_INFIX}*"
        result: dict[str, str] = {}
        async for key in self.redis.scan_iter(match=pattern, count=100):
            k = key if isinstance(key, str) else key.decode()
            obs_name = k.split(self.OBS_KEY_INFIX, 1)[1] if self.OBS_KEY_INFIX in k else k
            result[obs_name] = k
        return result

    async def _obs_keys_global(self, name: str | None = None) -> dict[str, str]:
        """Return {obs_name: redis_key} from the global observation index."""
        if name:
            return {name: f"{self.OBS_GLOBAL_PREFIX}{name}"}
        raw_names = await self.redis.smembers(self.OBS_INDEX_KEY)
        result: dict[str, str] = {}
        for n in raw_names:
            n_str = n if isinstance(n, str) else n.decode()
            result[n_str] = f"{self.OBS_GLOBAL_PREFIX}{n_str}"
        return result

    @staticmethod
    def _parse_obs_member(m: str, score: float) -> dict:
        """Parse 6-segment member format: {iso}:{value}:{unit}:{phase}:{event_id}:{service}.

        Falls back to 4-segment legacy format for pre-migration data.
        """
        segs = m.rsplit(":", 5)
        if len(segs) == 6:
            ts_str, val_str, u, ph, eid, svc = segs
        else:
            segs4 = m.rsplit(":", 3)
            if len(segs4) == 4:
                ts_str, val_str, u, ph = segs4
            else:
                ts_str, val_str, u, ph = m, "0", "", ""
            eid, svc = "", ""
        try:
            v = float(val_str)
        except ValueError:
            v = 0.0
        return {
            "timestamp": ts_str, "epoch": score, "value": v,
            "unit": u, "phase": ph, "event_id": eid, "service": svc,
        }

    async def get_observation_summary(self, event_id: str) -> Optional[dict]:
        """Compact observation summary for Archivist archival. Returns None if no observations."""
        data = await self.list_observations(event_id)
        if not data["observations"]:
            return None

        now = time.time()
        from datetime import datetime as _dt
        day_of_week = _dt.utcfromtimestamp(now).strftime("%A")
        time_of_day_utc = _dt.utcfromtimestamp(now).strftime("%H:%M")

        series_summaries = []
        for s in data["observations"]:
            values = [p["value"] for p in s["points"]]
            mean_val = sum(values) / len(values) if values else 0
            series_summaries.append({
                "name": s["name"],
                "trend": s["trend"],
                "peak": s["max"],
                "mean": round(mean_val, 2),
                "points": s["count"],
                "unit": s["unit"],
                "first_at": s["first_at"],
                "last_at": s["last_at"],
                "span_minutes": s["span_minutes"],
            })

        return {
            "event_duration_minutes": data["event_age_minutes"],
            "day_of_week": day_of_week,
            "time_of_day_utc": time_of_day_utc,
            "series": series_summaries,
        }

    # =========================================================================
    # Field Notes Notebook (qualitative knowledge capture)
    # =========================================================================
    NOTEBOOK_KEY = "darwin:notebook"
    NOTEBOOK_DIGESTING_KEY = "darwin:notebook:digesting"
    NOTEBOOK_QUARANTINE_KEY = "darwin:notebook:quarantine"
    NOTEBOOK_RETRY_KEY = "darwin:notebook:digesting:retries"
    NOTEBOOK_TTL_SECONDS = 604800  # 7 days
    MAX_NOTES = 200
    MAX_DIGEST_RETRIES = 3
    VALID_CATEGORIES = frozenset({
        "env-quirk", "correction", "cross-event", "workflow", "convention",
    })

    async def take_note(
        self, event_id: str, content: str, category: str,
    ) -> dict:
        """Record a qualitative field note. Returns {note_id, count}."""
        content = content[:2000]
        note_id = str(uuid.uuid4())
        note = json.dumps({
            "note_id": note_id,
            "content": content,
            "category": category,
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        pipe = self.redis.pipeline()
        pipe.hset(self.NOTEBOOK_KEY, note_id, note)
        pipe.expire(self.NOTEBOOK_KEY, self.NOTEBOOK_TTL_SECONDS)
        pipe.hlen(self.NOTEBOOK_KEY)
        results = await pipe.execute()
        count = results[2]

        if count > self.MAX_NOTES:
            all_notes = await self.redis.hgetall(self.NOTEBOOK_KEY)
            entries = []
            corrupt_ids = []
            for nid, raw in all_notes.items():
                nid_str = nid if isinstance(nid, str) else nid.decode()
                try:
                    entries.append((nid_str, json.loads(raw)))
                except (json.JSONDecodeError, TypeError):
                    corrupt_ids.append(nid_str)
            if corrupt_ids:
                await self.redis.hdel(self.NOTEBOOK_KEY, *corrupt_ids)
                count -= len(corrupt_ids)
            entries.sort(key=lambda x: x[1].get("timestamp", ""))
            excess = len(entries) - self.MAX_NOTES
            if excess > 0:
                to_remove = [p[0] for p in entries[:excess]]
                await self.redis.hdel(self.NOTEBOOK_KEY, *to_remove)
                count -= excess

        return {"note_id": note_id, "count": count}

    async def get_notes(self) -> list[dict]:
        """Return all notebook entries sorted by timestamp."""
        raw = await self.redis.hgetall(self.NOTEBOOK_KEY)
        notes = []
        for _, val in raw.items():
            v = val if isinstance(val, str) else val.decode()
            try:
                notes.append(json.loads(v))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Corrupt notebook entry skipped")
                continue
        notes.sort(key=lambda n: n.get("timestamp", ""))
        return notes

    _UPDATE_NOTE_LUA = """
local raw = redis.call('HGET', KEYS[1], ARGV[1])
if not raw then return 0 end
local note = cjson.decode(raw)
if ARGV[2] ~= '' then note['content'] = ARGV[2] end
if ARGV[3] ~= '' then note['category'] = ARGV[3] end
redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(note))
return 1
"""

    async def update_note(
        self, note_id: str, content: str | None = None, category: str | None = None,
    ) -> bool:
        """Atomically update a note's content and/or category via Lua. Returns False if not found."""
        result = await self.redis.eval(
            self._UPDATE_NOTE_LUA, 1, self.NOTEBOOK_KEY,
            note_id,
            content[:2000] if content is not None else "",
            category if category is not None else "",
        )
        return bool(result)

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note. Returns False if not found."""
        removed = await self.redis.hdel(self.NOTEBOOK_KEY, note_id)
        return removed > 0

    async def drain_notes(self) -> list[dict]:
        """Atomically move notebook to digesting key via RENAMENX.

        Returns [] if source empty or target already exists (orphan batch).
        """
        try:
            renamed = await self.redis.renamenx(
                self.NOTEBOOK_KEY, self.NOTEBOOK_DIGESTING_KEY,
            )
        except ResponseError as e:
            if "no such key" in str(e).lower():
                return []
            raise
        if not renamed:
            logger.warning(
                "Notebook drain skipped: digesting key exists (orphan batch)",
            )
            return []
        return await self.get_drained_notes()

    async def has_drained_notes(self) -> bool:
        """Check if an orphan digesting batch exists."""
        return bool(await self.redis.exists(self.NOTEBOOK_DIGESTING_KEY))

    async def get_drained_notes(self) -> list[dict]:
        """Read the digesting batch without removing it."""
        raw = await self.redis.hgetall(self.NOTEBOOK_DIGESTING_KEY)
        notes = []
        for _, val in raw.items():
            v = val if isinstance(val, str) else val.decode()
            try:
                notes.append(json.loads(v))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Corrupt digesting entry skipped")
                continue
        notes.sort(key=lambda n: n.get("timestamp", ""))
        return notes

    async def clear_drained_notes(self) -> None:
        """Delete the digesting key after successful digest."""
        pipe = self.redis.pipeline()
        pipe.delete(self.NOTEBOOK_DIGESTING_KEY)
        pipe.delete(self.NOTEBOOK_RETRY_KEY)
        await pipe.execute()

    async def quarantine_drained_notes(self) -> None:
        """Move failed digesting batch to timestamped quarantine key (no overwrite)."""
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        quarantine_key = f"{self.NOTEBOOK_QUARANTINE_KEY}:{ts}"
        try:
            await self.redis.rename(self.NOTEBOOK_DIGESTING_KEY, quarantine_key)
        except ResponseError:
            logger.warning("Quarantine rename failed (source missing?)")
        await self.redis.delete(self.NOTEBOOK_RETRY_KEY)
        await self.redis.expire(quarantine_key, self.NOTEBOOK_TTL_SECONDS)

    async def increment_digest_retries(self) -> int:
        """Increment and return the durable retry counter for the digesting batch."""
        pipe = self.redis.pipeline()
        pipe.incr(self.NOTEBOOK_RETRY_KEY)
        pipe.expire(self.NOTEBOOK_RETRY_KEY, self.NOTEBOOK_TTL_SECONDS)
        results = await pipe.execute()
        return results[0]

    # =========================================================================
    # Recently Closed Events (facade for route bypasses)
    # =========================================================================

    async def get_recently_closed_event_ids(
        self, limit: int = 50, since_seconds: int = 86400,
    ) -> list[str]:
        """Get closed event IDs within a time window (most recent first)."""
        now = time.time()
        return await self.redis.zrevrangebyscore(
            self.EVENT_CLOSED,
            max=now,
            min=now - since_seconds,
            start=0,
            num=limit,
        )

    async def get_all_closed_event_ids(self) -> list[str]:
        """Get all closed event IDs (oldest first). Used for bulk rebuild."""
        return await self.redis.zrange(self.EVENT_CLOSED, 0, -1)

    # =========================================================================
    # Cortex Shadow / Proposals / Handoff Reports (facade for route bypasses)
    # =========================================================================

    SHADOW_PREFIX = "darwin:cortex:shadow:"
    SHADOW_INDEX = "darwin:cortex:shadow:_index"
    HANDOFF_REPORTS_KEY = "darwin:cortex:handoff_reports"
    PROPOSALS_KEY = "darwin:cortex:proposals"
    PROPOSALS_DISMISSED_KEY = "darwin:cortex:proposals:dismissed"

    async def get_shadow_event_ids(self) -> list[str]:
        """Get event IDs that have shadow intervention data."""
        raw = await self.redis.smembers(self.SHADOW_INDEX)
        return [m if isinstance(m, str) else m.decode() for m in raw]

    async def get_shadow_interventions(self, event_id: str, limit: int = 50) -> list[dict]:
        """Get shadow intervention entries for a specific event."""
        raw_items = await self.redis.lrange(f"{self.SHADOW_PREFIX}{event_id}", -limit, -1)
        entries = []
        for raw in raw_items:
            try:
                entry = json.loads(raw)
                entry["event_id"] = event_id
                entries.append(entry)
            except (json.JSONDecodeError, TypeError):
                continue
        return entries

    async def get_handoff_reports(self, limit: int = 100) -> list[dict]:
        """Get JARVIS session handoff reports."""
        raw = await self.redis.lrange(self.HANDOFF_REPORTS_KEY, -limit, -1)
        reports = []
        for entry in raw:
            try:
                reports.append(json.loads(entry))
            except (json.JSONDecodeError, TypeError):
                continue
        reports.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return reports

    async def get_proposals(
        self, limit: int = 100, include_dismissed: bool = False,
    ) -> list[dict]:
        """Get JARVIS enhancement proposals, optionally including dismissed."""
        raw = await self.redis.lrange(self.PROPOSALS_KEY, -limit, -1)
        dismissed: set[str] = set()
        if not include_dismissed:
            dismissed = {
                m.decode() if isinstance(m, bytes) else m
                for m in await self.redis.smembers(self.PROPOSALS_DISMISSED_KEY)
            }
        proposals = []
        for entry in raw:
            try:
                p = json.loads(entry)
                ts_key = str(p.get("timestamp", ""))
                if ts_key in dismissed:
                    p["status"] = "dismissed"
                    if not include_dismissed:
                        continue
                proposals.append(p)
            except (json.JSONDecodeError, TypeError):
                continue
        proposals.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return proposals

    async def dismiss_proposals(self, timestamps: list) -> int:
        """Mark proposals as dismissed by timestamp."""
        str_timestamps = [str(t) for t in timestamps]
        await self.redis.sadd(self.PROPOSALS_DISMISSED_KEY, *str_timestamps)
        return len(str_timestamps)

    # =========================================================================
    # Jira Mission State (facade for route bypasses)
    # =========================================================================

    JIRA_MISSION_PREFIX = "darwin:headhunter:jira:"

    async def clear_jira_mission_state(self, issue_key: str) -> None:
        """Clear cached mission analysis state for a Jira issue."""
        await self.redis.delete(f"{self.JIRA_MISSION_PREFIX}{issue_key}")
