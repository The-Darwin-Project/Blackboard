// BlackBoard/ui/src/api/client.ts
// @ai-rules:
// 1. [Pattern]: All API calls go through fetchApi() wrapper -- consistent error handling via ApiError.
// 2. [Constraint]: closeEvent uses REST POST, not WebSocket -- ensures delivery even during WS reconnect.
// 3. [Pattern]: getEventReport fetches server-side markdown -- ConversationFeed falls back to client-side eventToMarkdown on failure.
/**
 * Typed API client for Darwin Brain backend.
 */
import type {
  ActiveEvent,
  AgentRegistryEntry,
  AppConfig,
  ArchitectureEvent,
  ChatEventRequest,
  ChatEventResponse,
  ChartData,
  EventDocument,
  GraphResponse,
  ReportFull,
  ReportMeta,
  Service,
  TopologyResponse,
} from './types';

// Base URL is proxied by Vite in development
const BASE_URL = '';

let _getToken: (() => string | null) | null = null;

/** Set the token getter for authenticated API calls. Called once by AuthProvider. */
export function setTokenGetter(getter: () => string | null) {
  _getToken = getter;
}

/**
 * Custom API error with detailed context.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly endpoint: string;
  readonly detail?: string;

  constructor(
    status: number,
    statusText: string,
    endpoint: string,
    detail?: string
  ) {
    super(`API Error [${status}] ${endpoint}: ${detail || statusText}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.endpoint = endpoint;
    this.detail = detail;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }
}

/**
 * Generic fetch wrapper with error handling.
 */
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: optHeaders, ...restOptions } = options;
  const authHeaders: Record<string, string> = {};
  const token = _getToken?.();
  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...optHeaders,
    },
  });

  if (!response.ok) {
    // Try to extract error detail from response body
    let detail: string | undefined;
    try {
      const errorBody = await response.json();
      detail = errorBody.detail || errorBody.message || errorBody.error;
    } catch {
      // Response body is not JSON or empty
    }
    throw new ApiError(response.status, response.statusText, endpoint, detail);
  }

  return response.json();
}

// =============================================================================
// Topology API
// =============================================================================

export async function getTopology(): Promise<TopologyResponse> {
  return fetchApi<TopologyResponse>('/topology/');
}

export async function getServices(): Promise<string[]> {
  return fetchApi<string[]>('/topology/services');
}

export async function getService(name: string): Promise<Service> {
  return fetchApi<Service>(`/topology/service/${encodeURIComponent(name)}`);
}

export async function getGraphData(): Promise<GraphResponse> {
  return fetchApi<GraphResponse>('/topology/graph');
}

// =============================================================================
// Metrics API
// =============================================================================

export async function getChartData(
  services: string[],
  rangeSeconds = 3600
): Promise<ChartData> {
  const params = new URLSearchParams();
  services.forEach(s => params.append('services', s));
  params.append('range_seconds', rangeSeconds.toString());
  
  return fetchApi<ChartData>(`/metrics/chart?${params.toString()}`);
}

export async function getCurrentMetrics(service: string): Promise<Record<string, number>> {
  return fetchApi<Record<string, number>>(`/metrics/${encodeURIComponent(service)}`);
}

// =============================================================================
// Queue API (event documents)
// =============================================================================

export async function getActiveEvents(): Promise<ActiveEvent[]> {
  return fetchApi<ActiveEvent[]>('/queue/active');
}

export async function getEventDocument(eventId: string): Promise<EventDocument> {
  return fetchApi<EventDocument>(`/queue/${encodeURIComponent(eventId)}`);
}

export async function approveEvent(eventId: string): Promise<unknown> {
  return fetchApi<unknown>(`/queue/${encodeURIComponent(eventId)}/approve`, {
    method: 'POST',
  });
}

export async function rejectEvent(eventId: string, reason: string, image?: string): Promise<unknown> {
  return fetchApi<unknown>(`/queue/${encodeURIComponent(eventId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, ...(image ? { image } : {}) }),
  });
}

export async function closeEvent(eventId: string, reason?: string): Promise<unknown> {
  return fetchApi<unknown>(`/queue/${encodeURIComponent(eventId)}/close`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason || 'User force-closed the event.' }),
  });
}

export async function getClosedEvents(limit?: number): Promise<ActiveEvent[]> {
  const params = limit ? `?limit=${limit}` : '';
  return fetchApi<ActiveEvent[]>(`/queue/closed/list${params}`);
}

export async function getEventReport(
  eventId: string
): Promise<{ markdown: string; event_id: string }> {
  return fetchApi<{ markdown: string; event_id: string }>(
    `/queue/${encodeURIComponent(eventId)}/report`
  );
}

// =============================================================================
// Events API
// =============================================================================

export async function getEvents(
  limit = 100,
  startTime?: number,
  endTime?: number,
  service?: string
): Promise<ArchitectureEvent[]> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  if (startTime !== undefined) params.append('start_time', startTime.toString());
  if (endTime !== undefined) params.append('end_time', endTime.toString());
  if (service !== undefined) params.append('service', service);
  
  return fetchApi<ArchitectureEvent[]>(`/events/?${params.toString()}`);
}

// =============================================================================
// Chat API (event-based)
// =============================================================================

export async function createChatEvent(
  message: string,
  service?: string
): Promise<ChatEventResponse> {
  const request: ChatEventRequest = { message, service };
  return fetchApi<ChatEventResponse>('/chat/', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// =============================================================================
// Reports API (persisted event snapshots)
// =============================================================================

export async function getReports(
  limit = 50,
  offset = 0,
  service?: string,
): Promise<ReportMeta[]> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  if (service) params.append('service', service);
  return fetchApi<ReportMeta[]>(`/reports/list?${params.toString()}`);
}

export async function getReport(eventId: string): Promise<ReportFull> {
  return fetchApi<ReportFull>(`/reports/${encodeURIComponent(eventId)}`);
}

// =============================================================================
// Incidents API (Smartsheet)
// =============================================================================

export interface Incident {
  date: string;
  platform: string;
  summary: string;
  reason: string;
  status: string;
  priority: string;
  affected_versions: string;
  labels: string;
  fix_pr: string;
  slack_thread: string;
  issue_key: string;
  sheet_url: string;
  [key: string]: string;
}

export async function getIncidents(): Promise<Incident[]> {
  return fetchApi<Incident[]>('/incidents/list');
}

// =============================================================================
// Agent Registry API (connected sidecars)
// =============================================================================

export async function getAgents(): Promise<AgentRegistryEntry[]> {
  return fetchApi<AgentRegistryEntry[]>('/api/agents');
}

// =============================================================================
// Headhunter Queue API
// =============================================================================

export interface HeadhunterTodo {
  todo_id: number;
  action: string;
  priority: number;
  mr_iid: number;
  mr_title: string;
  project_path: string;
  author: string;
  pipeline_status: string;
  created_at: string;
  target_url: string;
}

export async function getHeadhunterPending(): Promise<HeadhunterTodo[]> {
  return fetchApi<HeadhunterTodo[]>('/queue/headhunter/pending');
}

// =============================================================================
// Configuration API (AI Transparency & Compliance)
// =============================================================================

export async function getConfig(): Promise<AppConfig> {
  return fetchApi<AppConfig>('/config');
}

// =============================================================================
// Feedback API (AI Transparency & Compliance)
// =============================================================================

export async function submitFeedback(
  eventId: string,
  turnNumber: number,
  rating: 'positive' | 'negative',
  comment?: string,
): Promise<{ status: string }> {
  return fetchApi<{ status: string }>('/feedback', {
    method: 'POST',
    body: JSON.stringify({
      event_id: eventId,
      turn_number: turnNumber,
      rating,
      comment: comment || '',
    }),
  });
}

// =============================================================================
// TimeKeeper API (scheduled tasks)
// =============================================================================

export interface ScheduleItem {
  id: string;
  name: string;
  schedule_type: 'one_shot' | 'recurring';
  cron: string | null;
  fire_at: number;
  repo_url: string | null;
  mr_url: string | null;
  service: string | null;
  instructions: string;
  approval_mode: 'autonomous' | 'notify_and_wait';
  on_failure: 'notify' | 'close_event' | 'retry_once' | 'escalate_human';
  notify_emails: string[];
  domain: 'clear' | 'complicated';
  severity: 'info' | 'warning';
  created_by: string;
  enabled: boolean;
  last_fired: number | null;
}

export interface ScheduleCreatePayload {
  name: string;
  schedule_type: 'one_shot' | 'recurring';
  cron?: string | null;
  fire_at?: number | null;
  repo_url?: string | null;
  mr_url?: string | null;
  service?: string | null;
  instructions: string;
  approval_mode?: 'autonomous' | 'notify_and_wait';
  on_failure?: 'notify' | 'close_event' | 'retry_once' | 'escalate_human';
  notify_emails?: string[];
}

export async function getSchedules(): Promise<ScheduleItem[]> {
  return fetchApi<ScheduleItem[]>('/api/timekeeper');
}

export async function getSchedule(id: string): Promise<ScheduleItem> {
  return fetchApi<ScheduleItem>(`/api/timekeeper/${id}`);
}

export async function createSchedule(payload: ScheduleCreatePayload): Promise<{ id: string; status: string }> {
  return fetchApi('/api/timekeeper', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateSchedule(id: string, payload: ScheduleCreatePayload): Promise<{ id: string; status: string }> {
  return fetchApi(`/api/timekeeper/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteSchedule(id: string): Promise<{ id: string; status: string }> {
  return fetchApi(`/api/timekeeper/${id}`, { method: 'DELETE' });
}

export async function toggleSchedule(id: string): Promise<{ id: string; enabled: boolean }> {
  return fetchApi(`/api/timekeeper/${id}/toggle`, { method: 'PATCH' });
}

export async function refineInstructions(payload: {
  raw_intent: string;
  repo_url?: string | null;
  mr_url?: string | null;
  service?: string | null;
}): Promise<{ refined: string; reasoning: string }> {
  return fetchApi('/api/timekeeper/refine', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
