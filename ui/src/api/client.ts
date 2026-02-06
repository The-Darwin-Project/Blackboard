// BlackBoard/ui/src/api/client.ts
/**
 * Typed API client for Darwin Brain backend.
 */
import type {
  ArchitectureEvent,
  ChatEventRequest,
  ChatEventResponse,
  ChartData,
  EventDocument,
  GraphResponse,
  Service,
  TopologyResponse,
} from './types';

// Base URL is proxied by Vite in development
const BASE_URL = '';

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
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
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

export async function getActiveEvents(): Promise<any[]> {
  return fetchApi<any[]>('/queue/active');
}

export async function getEventDocument(eventId: string): Promise<EventDocument> {
  return fetchApi<EventDocument>(`/queue/${encodeURIComponent(eventId)}`);
}

export async function approveEvent(eventId: string): Promise<any> {
  return fetchApi<any>(`/queue/${encodeURIComponent(eventId)}/approve`, {
    method: 'POST',
  });
}

export async function getClosedEvents(limit?: number): Promise<any[]> {
  const params = limit ? `?limit=${limit}` : '';
  return fetchApi<any[]>(`/queue/closed/list${params}`);
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
