// BlackBoard/ui/src/hooks/useQueue.ts
/**
 * Queue hooks with hybrid hydration:
 * - Initial state from REST GET (on mount / reconnect)
 * - Incremental updates from WebSocket push
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getActiveEvents, getEventDocument } from '../api/client';

export function useActiveEvents() {
  return useQuery({
    queryKey: ['activeEvents'],
    queryFn: getActiveEvents,
    // No refetchInterval -- WebSocket handles incremental updates
    // Re-fetch on window focus for reconnect scenarios
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
