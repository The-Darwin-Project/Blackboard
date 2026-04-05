// BlackBoard/ui/src/hooks/useFlowMetrics.ts
import { useQuery } from '@tanstack/react-query';
import { getFlowMetrics } from '../api/client';
import type { FlowMetrics } from '../api/types';

const FLOW_POLL_INTERVAL = 10_000;

export function useFlowMetrics() {
  return useQuery<FlowMetrics>({
    queryKey: ['flow-metrics'],
    queryFn: getFlowMetrics,
    refetchInterval: FLOW_POLL_INTERVAL,
    staleTime: FLOW_POLL_INTERVAL,
    gcTime: 30_000,
  });
}
