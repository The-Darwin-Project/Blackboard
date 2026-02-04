// BlackBoard/ui/src/hooks/useTopology.ts
/**
 * TanStack Query hook for topology data.
 * Polls /topology/mermaid for diagram, /topology/ for details.
 */
import { useQuery } from '@tanstack/react-query';
import { getTopology, getTopologyMermaid, getService } from '../api/client';
import type { MermaidResponse, Service, TopologyResponse } from '../api/types';

// Polling interval: 2 seconds
const TOPOLOGY_POLL_INTERVAL = 2000;

/**
 * Hook for fetching topology mermaid diagram.
 */
export function useTopologyMermaid() {
  return useQuery<MermaidResponse>({
    queryKey: ['topology', 'mermaid'],
    queryFn: getTopologyMermaid,
    refetchInterval: TOPOLOGY_POLL_INTERVAL,
    staleTime: TOPOLOGY_POLL_INTERVAL,
  });
}

/**
 * Hook for fetching full topology with service details.
 */
export function useTopology() {
  return useQuery<TopologyResponse>({
    queryKey: ['topology'],
    queryFn: getTopology,
    refetchInterval: TOPOLOGY_POLL_INTERVAL,
    staleTime: TOPOLOGY_POLL_INTERVAL,
  });
}

/**
 * Hook for fetching a single service's details.
 */
export function useService(name: string | null) {
  return useQuery<Service>({
    queryKey: ['service', name],
    queryFn: () => getService(name!),
    enabled: !!name,
  });
}
