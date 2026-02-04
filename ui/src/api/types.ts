// BlackBoard/ui/src/api/types.ts
/**
 * TypeScript interfaces matching Python models.
 * Using snake_case to match API exactly (no transformation).
 */

// =============================================================================
// Enums
// =============================================================================

export type PlanStatus = 
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'executing'
  | 'completed'
  | 'failed';

export type PlanAction = 
  | 'scale'
  | 'rollback'
  | 'reconfig'
  | 'failover'
  | 'optimize';

export type EventType =
  | 'telemetry_received'
  | 'service_discovered'
  // Anomaly events (from Aligner)
  | 'high_cpu_detected'
  | 'high_error_rate_detected'
  | 'anomaly_resolved'
  // Plan lifecycle
  | 'plan_created'
  | 'plan_approved'
  | 'plan_rejected'
  | 'plan_executed'
  | 'plan_failed'
  // Architect autonomous
  | 'architect_analyzing';

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

export interface MermaidResponse {
  mermaid: string;
}

// =============================================================================
// Plans
// =============================================================================

export interface Plan {
  id: string;
  action: PlanAction;
  service: string;
  params: Record<string, unknown>;
  reason: string;
  status: PlanStatus;
  created_at: number;
  approved_at: number | null;
  executed_at: number | null;
  result: string | null;
}

export interface PlanCreate {
  action: PlanAction;
  service: string;
  params: Record<string, unknown>;
  reason: string;
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
}

// =============================================================================
// Chart Data
// =============================================================================

export interface ChartData {
  series: MetricSeries[];
  events: ArchitectureEvent[];
}

// =============================================================================
// Chat
// =============================================================================

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  message: string;
  plan_id: string | null;
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

export type Agent = 'aligner' | 'architect' | 'sysadmin';

export function getAgentFromEventType(eventType: EventType): Agent {
  switch (eventType) {
    // Aligner events (observation)
    case 'telemetry_received':
    case 'service_discovered':
    case 'high_cpu_detected':
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
    case 'plan_executed':
    case 'plan_failed':
      return 'sysadmin';
    default:
      return 'architect';
  }
}
