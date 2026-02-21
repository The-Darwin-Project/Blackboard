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
  | 'deferred'
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
  | 'aligner_observation'
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
    gitops_config_path?: string;
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

export interface TicketNode {
  event_id: string;
  status: EventStatus;
  source: string;
  reason: string;
  turn_count: number;
  elapsed_seconds: number;
  current_agent: string | null;
  defer_count: number;
  has_work_plan: boolean;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  plans: GhostNode[];
  tickets: TicketNode[];
}

// =============================================================================
// Message Status (read receipt protocol)
// =============================================================================

export type MessageStatus = 'sent' | 'delivered' | 'evaluated';

// =============================================================================
// Event Evidence (structured ticket data)
// =============================================================================

export interface EventMetrics {
  cpu: number;
  memory: number;
  error_rate: number;
  replicas: string;
}

export interface EventEvidence {
  display_text: string;
  source_type: string;
  domain: 'clear' | 'complicated' | 'complex' | 'chaotic';
  severity: 'info' | 'warning' | 'critical';
  metrics?: EventMetrics;
}

/** List-level event summary returned by /queue/active and /queue/closed/list. */
export interface ActiveEvent {
  id: string;
  source: string;
  service: string;
  status: EventStatus;
  reason: string;
  evidence: EventEvidence;
  turns: number;
  created: string;
}

// =============================================================================
// Event Queue (Brain conversation documents)
// =============================================================================

export interface EventInput {
  reason: string;
  evidence: EventEvidence;
  timeDate: string;
}

// TODO(dex): Add currentUser to WebSocket context for authenticated sessions
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
  image?: string;
  status?: MessageStatus;
  source?: string;
  user_name?: string;
  timestamp: number;
}

export interface EventDocument {
  id: string;
  source: 'aligner' | 'chat' | 'slack' | 'headhunter';
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
// Public Configuration (AI Transparency & Compliance)
// =============================================================================

export interface AppConfig {
  contactEmail: string;
  feedbackFormUrl: string;
  appVersion: string;
}

// =============================================================================
// Reports (persisted event snapshots)
// =============================================================================

export interface ReportMeta {
  event_id: string;
  service: string;
  source: string;
  domain: 'clear' | 'complicated' | 'complex' | 'chaotic';
  severity: 'info' | 'warning' | 'critical';
  turns: number;
  reason: string;
  closed_at: string;
}

export interface ReportFull extends ReportMeta {
  markdown: string;
}

// =============================================================================
// Agent Registry (connected sidecars)
// =============================================================================

export interface AgentRegistryEntry {
  agent_id: string;
  role: string;
  busy: boolean;
  current_event_id: string | null;
  current_task_id: string | null;
  connected_at: number;
  cli: string;
  model: string;
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
    case 'aligner_observation':
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
