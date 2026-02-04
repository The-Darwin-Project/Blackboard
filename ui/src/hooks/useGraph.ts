// BlackBoard/ui/src/hooks/useGraph.ts
/**
 * TanStack Query hook for graph data (Cytoscape.js visualization).
 */
import { useQuery } from '@tanstack/react-query';
import { getGraphData } from '../api/client';
import type { GraphResponse } from '../api/types';

// Polling interval: 5 seconds (matches metrics)
const GRAPH_POLL_INTERVAL = 5000;

/**
 * Hook for fetching graph data for Cytoscape visualization.
 * 
 * Returns nodes, edges, and ghost nodes (pending plans).
 */
export function useGraph() {
  return useQuery<GraphResponse>({
    queryKey: ['topology', 'graph'],
    queryFn: getGraphData,
    refetchInterval: GRAPH_POLL_INTERVAL,
    staleTime: GRAPH_POLL_INTERVAL,
  });
}
