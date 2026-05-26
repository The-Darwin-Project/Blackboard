// BlackBoard/ui/src/hooks/useJira.ts
// @ai-rules:
// 1. [Pattern]: Same react-query polling pattern as useHeadhunterPending (10s interval).
// 2. [Pattern]: useJiraActions invalidates queryKey after each mutation for instant UI refresh.
// 3. [Constraint]: No optimistic updates -- Jira API latency makes stale reads acceptable.
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getJiraMissions, postJiraAction } from '../api/client';

export function useJiraMissions() {
  return useQuery({
    queryKey: ['jiraMissions'],
    queryFn: getJiraMissions,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });
}

export function useJiraActions() {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['jiraMissions'] });

  return {
    approve: async (key: string) => { await postJiraAction(key, 'approve'); invalidate(); },
    reanalyze: async (key: string) => { await postJiraAction(key, 'reanalyze'); invalidate(); },
    dismiss: async (key: string) => { await postJiraAction(key, 'dismiss'); invalidate(); },
  };
}
