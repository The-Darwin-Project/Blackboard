// BlackBoard/ui/src/hooks/usePlans.ts
/**
 * TanStack Query hook for plans data.
 * Fetches /plans/, provides approve/reject mutations.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { approvePlan, getPlans, rejectPlan } from '../api/client';
import type { Plan } from '../api/types';

// Polling interval: 3 seconds
const PLANS_POLL_INTERVAL = 3000;

/**
 * Hook for fetching plans.
 */
export function usePlans(status?: string) {
  return useQuery<Plan[]>({
    queryKey: ['plans', status],
    queryFn: () => getPlans(status),
    refetchInterval: PLANS_POLL_INTERVAL,
    staleTime: PLANS_POLL_INTERVAL,
  });
}

/**
 * Hook for approving a plan.
 */
export function useApprovePlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => approvePlan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}

/**
 * Hook for rejecting a plan.
 */
export function useRejectPlan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      rejectPlan(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}
