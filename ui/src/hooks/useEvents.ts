// BlackBoard/ui/src/hooks/useEvents.ts
/**
 * TanStack Query hook for events data.
 * Fetches /events/ for agent activity stream.
 * Supports optional service filtering.
 */
import { useQuery } from '@tanstack/react-query';
import { getEvents } from '../api/client';
import type { ArchitectureEvent } from '../api/types';

// Polling interval: 30 seconds (reduced from 5s to save memory)
const EVENTS_POLL_INTERVAL = 30000;

/**
 * Hook for fetching architecture events.
 * @param limit - Maximum number of events to fetch (default: 20, reduced from 100)
 * @param service - Optional service name to filter events by
 */
export function useEvents(limit = 20, service?: string) {
  return useQuery<ArchitectureEvent[]>({
    queryKey: ['events', limit, service],
    queryFn: () => getEvents(limit, undefined, undefined, service),
    refetchInterval: EVENTS_POLL_INTERVAL,
    staleTime: EVENTS_POLL_INTERVAL,
    gcTime: 60000, // Garbage collect stale cache after 60s
  });
}
