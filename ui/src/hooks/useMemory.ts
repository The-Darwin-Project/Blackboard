// BlackBoard/ui/src/hooks/useMemory.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMemories,
  correctMemory,
  getLessons,
  createLesson,
  deleteLesson,
  extractLessons,
  applyLessons,
  getClosedEvents,
} from '../api/client';

export function useMemories() {
  return useQuery({
    queryKey: ['memories'],
    queryFn: getMemories,
    refetchInterval: 120_000,
  });
}

export function useLessons() {
  return useQuery({
    queryKey: ['lessons'],
    queryFn: getLessons,
    refetchInterval: 120_000,
  });
}

export function useCorrectMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: correctMemory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['memories'] }),
  });
}

export function useCreateLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createLesson,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lessons'] }),
  });
}

export function useDeleteLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => deleteLesson(lessonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lessons'] }),
  });
}

export function useExtractLessons() {
  return useMutation({ mutationFn: extractLessons });
}

export function useApplyLessons() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: applyLessons,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memories'] });
      qc.invalidateQueries({ queryKey: ['lessons'] });
    },
  });
}

export function useClosedEvents() {
  return useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(100),
    staleTime: 60_000,
  });
}
