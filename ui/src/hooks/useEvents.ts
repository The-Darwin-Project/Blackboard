// BlackBoard/ui/src/hooks/useEvents.ts
/**
 * TanStack Query hook for events data.
 * Fetches /events/ for agent activity stream.
 */
import { useQuery } from '@tanstack/react-query';
import { getEvents } from '../api/client';
import type { ArchitectureEvent } from '../api/types';

// Polling interval: 5 seconds
const EVENTS_POLL_INTERVAL = 5000;

/**
 * Hook for fetching architecture events.
 */
export function useEvents(limit = 100) {
  return useQuery<ArchitectureEvent[]>({
    queryKey: ['events', limit],
    queryFn: () => getEvents(limit),
    refetchInterval: EVENTS_POLL_INTERVAL,
    staleTime: EVENTS_POLL_INTERVAL,
  });
}
