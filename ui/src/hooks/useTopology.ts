// BlackBoard/ui/src/hooks/useTopology.ts
/**
 * TanStack Query hook for topology data.
 * Polls /topology/ for details.
 */
import { useQuery } from '@tanstack/react-query';
import { ApiError, getTopology, getService } from '../api/client';
import type { Service, TopologyResponse } from '../api/types';

// Polling interval: 15 seconds (reduced from 2s -- topology rarely changes)
const TOPOLOGY_POLL_INTERVAL = 15000;

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
 * Returns null data (not error) for 404s to handle gracefully.
 */
export function useService(name: string | null) {
  return useQuery<Service | null>({
    queryKey: ['service', name],
    queryFn: async () => {
      try {
        return await getService(name!);
      } catch (error) {
        // Treat 404 as "not found" rather than error
        if (error instanceof ApiError && error.isNotFound) {
          return null;
        }
        throw error;
      }
    },
    enabled: !!name,
    retry: (failureCount, error) => {
      // Don't retry 404s
      if (error instanceof ApiError && error.isNotFound) {
        return false;
      }
      return failureCount < 2;
    },
  });
}
