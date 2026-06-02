// BlackBoard/ui/src/hooks/useObservations.ts
// @ai-rules:
// 1. [Pattern]: TanStack Query hook, same pattern as useIncidents/useQueue.
// 2. [Constraint]: 15s poll on active events, static for closed. Keyed by eventId.
// 3. [Pattern]: Two modes -- global (no eventId) and event-scoped (eventId set).
import { useQuery } from '@tanstack/react-query';
import { getEventObservations, getGlobalObservations } from '../api/client';
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

export function useGlobalObservations(filters?: { name?: string; service?: string }) {
  return useQuery<ObservationsResponse>({
    queryKey: ['observations', 'global', filters?.name, filters?.service],
    queryFn: () => getGlobalObservations(filters),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });
}
