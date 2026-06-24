// BlackBoard/ui/src/hooks/useMemory.ts
// @ai-rules:
// 1. [Pattern]: React Query hooks for Archivist collections (memories, lessons, knowledge).
// 2. [Pattern]: Every mutation invalidates its own query key on success.
// 3. [Constraint]: Knowledge hooks mirror lesson hooks but add updateKnowledge (PATCH support).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMemories,
  correctMemory,
  getLessons,
  createLesson,
  deleteLesson,
  extractLessons,
  applyLessons,
  getKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
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

// =============================================================================
// Knowledge Facts (darwin_knowledge)
// =============================================================================

export function useKnowledge() {
  return useQuery({
    queryKey: ['knowledge'],
    queryFn: () => getKnowledge(),
    refetchInterval: 120_000,
  });
}

export function useCreateKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createKnowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
    onError: (err) => console.error('[knowledge] create failed:', err),
  });
}

export function useUpdateKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      id: string;
      updates: { fact?: string; source?: string; confidence?: number; valid_until?: number | null };
    }) => updateKnowledge(vars.id, vars.updates),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
    onError: (err) => console.error('[knowledge] update failed:', err),
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteKnowledge(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
    onError: (err) => console.error('[knowledge] delete failed:', err),
  });
}

