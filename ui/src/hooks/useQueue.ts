// BlackBoard/ui/src/hooks/useQueue.ts
// @ai-rules:
// 1. [Pattern]: Hybrid hydration -- REST on mount, WS for incremental, polling as safety net.
// 2. [Gotcha]: refetchInterval on activeEvents catches missed WS event_closed messages (ghost events).
/**
 * Queue hooks with hybrid hydration:
 * - Initial state from REST GET (on mount / reconnect)
 * - Incremental updates from WebSocket push
 * - Polling safety net (10s) to catch missed WS messages
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getActiveEvents, getEventDocument } from '../api/client';

export function useActiveEvents() {
  return useQuery({
    queryKey: ['activeEvents'],
    queryFn: getActiveEvents,
    // 10s polling safety net: catches ghost events when WS event_closed was
    // sent to a dead connection (e.g., page refresh during active processing).
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });
}

export function useEventDocument(eventId: string | null) {
  return useQuery({
    queryKey: ['eventDocument', eventId],
    queryFn: () => getEventDocument(eventId!),
    enabled: !!eventId,
    // No refetchInterval -- WebSocket pushes updates
    refetchOnWindowFocus: true,
    // Don't retry 404s -- event was cleaned up (pod restart, Redis flush)
    retry: (failureCount, error) => {
      if (error && 'status' in error && (error as any).status === 404) return false;
      return failureCount < 2;
    },
  });
}

/**
 * Hook to invalidate queue queries (called by WebSocket message handler).
 */
export function useQueueInvalidation() {
  const queryClient = useQueryClient();
  return {
    invalidateActive: () => queryClient.invalidateQueries({ queryKey: ['activeEvents'] }),
    invalidateEvent: (eventId: string) => queryClient.invalidateQueries({ queryKey: ['eventDocument', eventId] }),
    invalidateAll: () => {
      queryClient.invalidateQueries({ queryKey: ['activeEvents'] });
      queryClient.invalidateQueries({ queryKey: ['eventDocument'] });
    },
  };
}
