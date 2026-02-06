// BlackBoard/ui/src/api/types.ts
/**
 * TypeScript interfaces matching Python models.
 * Using snake_case to match API exactly (no transformation).
 */

// =============================================================================
// Enums
// =============================================================================

export type EventStatus =
  | 'new'
  | 'active'
  | 'waiting_approval'
  | 'resolved'
  | 'closed';

export type EventType =
  | 'telemetry_received'
  | 'service_discovered'
  // Drift detection
  | 'deployment_detected'
  // Anomaly events (from Aligner)
  | 'high_cpu_detected'
  | 'high_memory_detected'
  | 'high_error_rate_detected'
  | 'anomaly_resolved'
  // Plan lifecycle
  | 'plan_created'
  | 'plan_approved'
  | 'plan_rejected'
  | 'plan_executed'
  | 'plan_failed'
  // Architect autonomous
  | 'architect_analyzing'
  // SysAdmin execution
  | 'sysadmin_executing';

// =============================================================================
// Service & Topology
// =============================================================================

export interface Metrics {
  cpu: number;
  memory: number;
  error_rate: number;
}

export interface Dependency {
  target: string;
  type: string;
  env_var: string | null;
}

export interface Service {
  name: string;
  version: string;
  metrics: Metrics;
  dependencies: string[];
  last_seen: number;
}

export interface TopologySnapshot {
  services: string[];
  edges: Record<string, string[]>;
}

export interface TopologyResponse {
  services: Record<string, Service>;
  edges: Record<string, string[]>;
}

// =============================================================================
// Graph Visualization (Cytoscape.js)
// =============================================================================

export type NodeType = 'service' | 'database' | 'cache' | 'external';
export type HealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  metadata: {
    version: string;
    health: HealthStatus;
    cpu: number;
    memory: number;
    error_rate: number;
    last_seen: number;
    gitops_repo?: string;
    gitops_repo_url?: string;
    gitops_helm_path?: string;
    replicas_ready?: number;
    replicas_desired?: number;
  };
}

export interface GraphEdge {
  source: string;
  target: string;
  protocol: string;
  type: string;  // 'hard' or 'async'
}

export interface GhostNode {
  plan_id: string;
  target_node: string;
  action: string;
  status: string;
  params: Record<string, unknown>;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  plans: GhostNode[];
}

// =============================================================================
// Event Queue (Brain conversation documents)
// =============================================================================

export interface EventInput {
  reason: string;
  evidence: string;
  timeDate: string;
}

export interface ConversationTurn {
  turn: number;
  actor: string;
  action: string;
  thoughts?: string;
  result?: string;
  plan?: string;
  selectedAgents?: string[];
  taskForAgent?: Record<string, unknown>;
  requestingAgent?: string;
  executed?: boolean;
  evidence?: string;
  waitingFor?: string;
  pendingApproval?: boolean;
  timestamp: number;
}

export interface EventDocument {
  id: string;
  source: 'aligner' | 'chat';
  status: EventStatus;
  service: string;
  event: EventInput;
  conversation: ConversationTurn[];
}

// =============================================================================
// Metrics History
// =============================================================================

export interface MetricPoint {
  timestamp: number;
  value: number;
}

export interface MetricSeries {
  service: string;
  metric: string;
  data: MetricPoint[];
}

// =============================================================================
// Architecture Events
// =============================================================================

export interface ArchitectureEvent {
  type: EventType;
  timestamp: number;
  details: Record<string, unknown>;
  narrative?: string;  // Human-readable explanation of the event
}

// =============================================================================
// Chart Data
// =============================================================================

export interface ChartData {
  series: MetricSeries[];
  events: ArchitectureEvent[];
}

// =============================================================================
// Chat (event-based)
// =============================================================================

export interface ChatEventRequest {
  message: string;
  service?: string;
}

export interface ChatEventResponse {
  event_id: string;
  status: string;
}

// =============================================================================
// Health
// =============================================================================

export interface HealthResponse {
  status: string;
}

// =============================================================================
// Agent Mapping Helper
// =============================================================================

export type Agent = 'aligner' | 'architect' | 'sysadmin' | 'developer' | 'brain';

export function getAgentFromEventType(eventType: EventType): Agent {
  switch (eventType) {
    // Aligner events (observation)
    case 'telemetry_received':
    case 'service_discovered':
    case 'deployment_detected':
    case 'high_cpu_detected':
    case 'high_memory_detected':
    case 'high_error_rate_detected':
    case 'anomaly_resolved':
      return 'aligner';
    // Architect events (strategy)
    case 'plan_created':
    case 'plan_approved':
    case 'plan_rejected':
    case 'architect_analyzing':
      return 'architect';
    // SysAdmin events (execution)
    case 'sysadmin_executing':
    case 'plan_executed':
    case 'plan_failed':
      return 'sysadmin';
    default:
      return 'architect';
  }
}
