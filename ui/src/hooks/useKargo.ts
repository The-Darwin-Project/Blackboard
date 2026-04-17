// BlackBoard/ui/src/hooks/useKargo.ts
// @ai-rules:
// 1. [Pattern]: Hybrid hydration -- REST on mount + polling safety net, WS for real-time via cache set.
// 2. [Pattern]: Matches useActiveEvents in useQueue.ts. 30s poll (Kargo promotions change infrequently).
// 3. [Constraint]: initialData prevents undefined before first fetch -- consumers always get KargoStageStatus[].
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getKargoStages } from '../api/client';
import type { KargoStageStatus } from '../api/types';

export const KARGO_STAGES_KEY = ['kargoStages'] as const;

export function useKargoStages() {
  return useQuery({
    queryKey: KARGO_STAGES_KEY,
    queryFn: getKargoStages,
    initialData: [] as KargoStageStatus[],
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });
}

export function useKargoStagesInvalidation() {
  const queryClient = useQueryClient();
  return {
    setKargoStages: (stages: KargoStageStatus[]) =>
      queryClient.setQueryData<KargoStageStatus[]>(KARGO_STAGES_KEY, stages),
    invalidateKargoStages: () =>
      queryClient.invalidateQueries({ queryKey: KARGO_STAGES_KEY }),
  };
}
