// BlackBoard/ui/src/hooks/useMetrics.ts
/**
 * TanStack Query hook for metrics data.
 * Fetches /metrics/chart, defaults to all services if none provided.
 */
import { useQuery } from '@tanstack/react-query';
import { getChartData, getServices } from '../api/client';
import type { ChartData } from '../api/types';

// Polling interval: 5 seconds
const METRICS_POLL_INTERVAL = 5000;

/**
 * Hook for fetching chart data for specified services.
 * If services is undefined/empty, fetches all services first.
 */
export function useMetrics(services?: string[], rangeSeconds = 3600) {
  // First fetch services if not provided
  const servicesQuery = useQuery<string[]>({
    queryKey: ['services'],
    queryFn: getServices,
    enabled: !services || services.length === 0,
    staleTime: 30000, // Cache services list for 30 seconds
  });

  // Determine which services to use
  const effectiveServices = services?.length ? services : servicesQuery.data ?? [];

  // Fetch chart data
  return useQuery<ChartData>({
    queryKey: ['metrics', 'chart', effectiveServices, rangeSeconds],
    queryFn: () => getChartData(effectiveServices, rangeSeconds),
    enabled: effectiveServices.length > 0,
    refetchInterval: METRICS_POLL_INTERVAL,
    staleTime: METRICS_POLL_INTERVAL,
  });
}
