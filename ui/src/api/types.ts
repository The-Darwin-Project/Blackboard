// BlackBoard/ui/src/api/types.ts
// @ai-rules:
// 1. [Constraint]: All interfaces use snake_case to match Python API exactly -- no camelCase transformation.
// 2. [Pattern]: GraphResponse is the /topology/graph contract: nodes + edges + tickets. No plans field.
// 3. [Pattern]: TicketNode.resolved_service is nullable -- populated by future probe heuristic (currently always null from backend).
// 4. [Pattern]: getAgentFromEventType() maps EventType to agent name for UI coloring. Keep in sync with Python EventType enum.
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
  // Architect autonomous
  | 'architect_analyzing'
  // SysAdmin execution
  | 'sysadmin_executing'
  // Brain lifecycle
  | 'brain_event_created'
  | 'brain_agent_routed'
  | 'brain_event_closed'
  | 'brain_event_deferred';

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

export interface TicketNode {
  event_id: string;
  status: EventStatus;
  source: string;
  reason: string;
  turn_count: number;
  elapsed_seconds: number;
  current_agent: string | null;
  defer_count: number;
  defer_until?: number | null;
  defer_started_at?: number | null;
  has_work_plan: boolean;
  resolved_service: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
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
  triggered_by?: string | null;
  domain: 'disorder' | 'clear' | 'complicated' | 'complex' | 'chaotic';
  brain_domain?: string;
  brain_severity?: 'info' | 'warning' | 'critical';
  domain_confidence?: 'assessed' | 'default';
  severity: 'info' | 'warning' | 'critical';
  metrics?: EventMetrics;
  kargo_context?: Record<string, string>;
}

/** List-level event summary returned by /queue/active and /queue/closed/list. */
export type SubjectType = 'service' | 'kargo_stage' | 'system' | 'jira';

export interface ActiveEvent {
  id: string;
  source: string;
  service: string;
  subject_type?: SubjectType;
  status: EventStatus;
  reason: string;
  evidence: EventEvidence;
  turns: number;
  created: string;
  unread_notes?: number;
  /** Unix seconds when FRIDAY's defer timer fires (from Redis). */
  defer_until?: number;
  /** Unix seconds of the last brain.defer turn (conversation). */
  defer_started_at?: number;
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

export type EventSource = 'aligner' | 'chat' | 'slack' | 'headhunter' | 'timekeeper' | 'jarvis';

export interface EventDocument {
  id: string;
  source: EventSource;
  status: EventStatus;
  brain_phase?: string;
  service: string;
  subject_type?: SubjectType;
  event: EventInput;
  conversation: ConversationTurn[];
  sticky_notes?: Array<{ timestamp: string; content: string; read: boolean }>;
  unread_notes?: number;
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
// Flow Observability
// =============================================================================

export interface FlowMetrics {
  queue_depth: number;
  active_events: number;
  busy_agents: number;
  idle_agents: number;
  agents_by_role: Record<string, { busy: number; idle: number }>;
}

// =============================================================================
// Public Configuration (AI Transparency & Compliance)
// =============================================================================

export interface AuthConfig {
  enabled: boolean;
  issuerUrl?: string;
  clientId?: string;
  loginDisclaimer?: string;
}

export interface AuthUser {
  sub: string;
  name: string;
  email: string;
  groups?: string[];
}

export interface AppConfig {
  contactEmail: string;
  feedbackFormUrl: string;
  appVersion: string;
  auth?: AuthConfig;
  nightwatcher?: { enabled: boolean };
}

// =============================================================================
// Shifts (Nightwatcher)
// =============================================================================

export interface ShiftReportSummary {
  shift_date: string;
  window: 'morning' | 'evening';
  status: 'completed' | 'running' | 'empty' | 'failed';
  escalation_count: number;
  incident_count: number;
  noise_reduction_pct: number;
}

export interface StagedEscalationDTO {
  event_id: string;
  service: string;
  source: string;
  platform: string;
  priority: string;
  summary: string;
  description: string;
  staged_at: number;
}

export interface ShiftIncidentDTO {
  platform: string;
  summary: string;
  description: string;
  priority: string;
  status: string;
  affected_events: string[];
  smartsheet_row_id: string;
  smartsheet_url: string;
}

export interface ShiftInvestigationDTO {
  task: string;
  service: string;
  agent_result: string;
  duration_seconds: number;
  cluster_id: string;
}

export interface ShiftReportFull {
  shift_date: string;
  window: 'morning' | 'evening';
  window_start: string;
  window_end: string;
  status: 'completed' | 'running' | 'empty' | 'failed';
  manifest: StagedEscalationDTO[];
  incidents: ShiftIncidentDTO[];
  investigations: ShiftInvestigationDTO[];
  summary_text: string;
  metrics: Record<string, number>;
  started_at: number | null;
  completed_at: number | null;
}

export interface ShiftCurrentStatus {
  pending_count: number;
  next_sweep_utc: string;
  enabled: boolean;
}

// =============================================================================
// Reports (persisted event snapshots)
// =============================================================================

export interface ReportMeta {
  event_id: string;
  service: string;
  source: string;
  subject_type?: SubjectType;
  domain: 'disorder' | 'clear' | 'complicated' | 'complex' | 'chaotic';
  severity: 'info' | 'warning' | 'critical';
  turns: number;
  reason: string;
  closed_at: string;
  indexed_at?: number;
  triggered_by?: string | null;
}

export interface ReportSearchResponse {
  items: ReportMeta[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ReportFull extends ReportMeta {
  markdown: string;
}

// =============================================================================
// Kargo Stage Status (failed promotion snapshots from KargoObserver)
// =============================================================================

export interface KargoStageStatus {
  project: string;
  stage: string;
  promotion: string;
  phase: string;
  message: string;
  failed_step: string;
  service: string;
  mr_url: string;
  started_at?: string;
  finished_at?: string;
}

// =============================================================================
// Jira Missions (Headhunter tracked issues)
// =============================================================================

export interface JiraMission {
  key: string;
  summary: string;
  status: string;
  priority: string;
  labels: string[];
  phase: 'pending' | 'analyzed' | 'approved' | 'executing';
  issue_url: string;
  analysis: string | null;
}

// =============================================================================
// Observations (FRIDAY numeric series per event)
// =============================================================================

export interface ObservationPoint {
  timestamp: string;
  epoch: number;
  value: number;
  unit: string;
  phase: string;
  event_id: string;
  service: string;
}

export interface ObservationSeries {
  name: string;
  count: number;
  min: number;
  max: number;
  latest_value: number;
  unit: string;
  first_at: string;
  last_at: string;
  span_minutes: number;
  trend: 'rising' | 'falling' | 'stable';
  points: ObservationPoint[];
}

export interface ObservationsResponse {
  event_id: string;
  event_opened: string;
  event_age_minutes: number;
  observations: ObservationSeries[];
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
  ephemeral?: boolean;
  bound_event_id?: string | null;
  current_role?: string | null;
}

// =============================================================================
// Agent Mapping Helper
// =============================================================================

export type Agent = 'aligner' | 'architect' | 'sysadmin' | 'developer' | 'security_analyst' | 'brain';

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
    case 'architect_analyzing':
      return 'architect';
    // SysAdmin events (execution)
    case 'sysadmin_executing':
      return 'sysadmin';
    // Brain lifecycle events
    case 'brain_event_created':
    case 'brain_agent_routed':
    case 'brain_event_closed':
    case 'brain_event_deferred':
      return 'brain';
    default:
      return 'architect';
  }
}
