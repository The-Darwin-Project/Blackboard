// BlackBoard/ui/src/hooks/useConfig.ts
// @ai-rules:
// 1. [Pattern]: Follows same TanStack Query pattern as useTopology, useQueue, etc.
// 2. [Constraint]: staleTime=Infinity -- config is static at runtime, never refetched.
// 3. [Pattern]: Consumed by GuidePage and Layout footer. Single cached fetch shared across components.
import { useQuery } from '@tanstack/react-query';
import { getConfig } from '../api/client';
import type { AppConfig } from '../api/types';

export function useConfig() {
  return useQuery<AppConfig>({
    queryKey: ['config'],
    queryFn: getConfig,
    staleTime: Infinity,
  });
}
