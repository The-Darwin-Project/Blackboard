// BlackBoard/ui/src/hooks/useIncidents.ts
import { useQuery } from '@tanstack/react-query';
import { getIncidents } from '../api/client';

export function useIncidents() {
  return useQuery({
    queryKey: ['incidents'],
    queryFn: getIncidents,
    refetchInterval: 60_000,
  });
}
