// BlackBoard/ui/src/hooks/useObservations.ts
// @ai-rules:
// 1. [Pattern]: TanStack Query hook, same pattern as useIncidents/useQueue.
// 2. [Constraint]: 15s poll on active events, static for closed. Keyed by eventId.
import { useQuery } from '@tanstack/react-query';
import { getEventObservations } from '../api/client';
import type { ObservationsResponse } from '../api/types';

export function useObservations(eventId: string | null, isActive: boolean) {
  return useQuery<ObservationsResponse>({
    queryKey: ['observations', eventId],
    queryFn: () => getEventObservations(eventId!),
    enabled: !!eventId,
    refetchInterval: isActive ? 15_000 : false,
    staleTime: isActive ? 10_000 : 60_000,
  });
}
