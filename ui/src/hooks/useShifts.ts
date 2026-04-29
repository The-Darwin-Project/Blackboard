// BlackBoard/ui/src/hooks/useShifts.ts
// @ai-rules:
// 1. [Pattern]: Follows useIncidents.ts pattern -- TanStack React Query with typed responses.
// 2. [Pattern]: useCurrentShift polls at 60s (matching useIncidents). useShiftsList has 5min stale time.
import { useQuery } from '@tanstack/react-query';
import { getShiftsList, getShiftDetail, getCurrentShift } from '../api/client';

export function useCurrentShift() {
  return useQuery({
    queryKey: ['shifts', 'current'],
    queryFn: getCurrentShift,
    refetchInterval: 60_000,
  });
}

export function useShiftsList(week: string) {
  return useQuery({
    queryKey: ['shifts', 'list', week],
    queryFn: () => getShiftsList(week),
    staleTime: 5 * 60_000,
    enabled: !!week,
  });
}

export function useShiftDetail(date: string, window: string) {
  return useQuery({
    queryKey: ['shifts', 'detail', date, window],
    queryFn: () => getShiftDetail(date, window),
    enabled: !!date && !!window,
  });
}
