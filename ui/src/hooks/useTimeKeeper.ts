// BlackBoard/ui/src/hooks/useTimeKeeper.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSchedule,
  deleteSchedule,
  getSchedules,
  refineInstructions,
  toggleSchedule,
  updateSchedule,
} from '../api/client';
import type { ScheduleCreatePayload } from '../api/client';

const QUERY_KEY = ['timekeeper-schedules'];

export function useSchedules() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: getSchedules,
    refetchInterval: 30_000,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScheduleCreatePayload) => createSchedule(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ScheduleCreatePayload }) =>
      updateSchedule(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useToggleSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => toggleSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: QUERY_KEY }),
  });
}

export function useRefineInstructions() {
  return useMutation({
    mutationFn: (payload: {
      raw_intent: string;
      repo_url?: string | null;
      mr_url?: string | null;
      service?: string | null;
    }) => refineInstructions(payload),
  });
}
