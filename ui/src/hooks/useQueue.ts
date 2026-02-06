// BlackBoard/ui/src/hooks/useQueue.ts
/**
 * TanStack Query hooks for the event queue.
 * Polls active events and fetches individual event documents.
 */
import { useQuery } from '@tanstack/react-query';
import { getActiveEvents, getEventDocument } from '../api/client';

export function useActiveEvents() {
  return useQuery({
    queryKey: ['activeEvents'],
    queryFn: getActiveEvents,
    refetchInterval: 3000,
  });
}

export function useEventDocument(eventId: string | null) {
  return useQuery({
    queryKey: ['eventDocument', eventId],
    queryFn: () => getEventDocument(eventId!),
    enabled: !!eventId,
    refetchInterval: 2000,
  });
}
