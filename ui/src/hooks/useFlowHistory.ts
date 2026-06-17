// BlackBoard/ui/src/hooks/useFlowHistory.ts
import { useQuery } from '@tanstack/react-query';
import { getFlowHistory } from '../api/client';
import type { FlowSnapshot } from '../api/types';

export function useFlowHistory(rangeSeconds: number = 3600) {
  return useQuery<FlowSnapshot[]>({
    queryKey: ['flow-history', rangeSeconds],
    queryFn: () => getFlowHistory(rangeSeconds),
    refetchInterval: 30_000,
    staleTime: 30_000,
  });
}
