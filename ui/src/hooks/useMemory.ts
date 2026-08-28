// BlackBoard/ui/src/hooks/useMemory.ts
// @ai-rules:
// 1. [Pattern]: React Query hooks for Archivist collections (memories, lessons, knowledge).
// 2. [Pattern]: Every mutation invalidates its own query key on success.
// 3. [Constraint]: Knowledge hooks mirror lesson hooks but add updateKnowledge (PATCH support).
// 4. [Pattern]: useKnowledgeScroll/useLessonsScroll/useMemoriesScroll are useInfiniteQuery clones
//    of useReportSearch.ts -- PAGE_SIZE 50, getNextPageParam reads has_more/next_cursor. Query key
//    includes filters so TanStack Query auto-refetches on filter change. Mutations invalidate the
//    base key (e.g. ['knowledgeScroll']) which matches ALL filter variants via partial key match.
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  scrollMemories,
  correctMemory,
  scrollLessons,
  getLessonById,
  createLesson,
  deleteLesson,
  extractLessons,
  applyLessons,
  scrollKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
} from '../api/client';

const PAGE_SIZE = 50;

// =============================================================================
// Event Memories (darwin_events)
// =============================================================================

export interface MemoriesScrollFilters {
  service?: string;
  q?: string;
}

export function useMemoriesScroll(filters: MemoriesScrollFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['memoriesScroll', filters],
    queryFn: ({ pageParam }) =>
      scrollMemories({
        limit: PAGE_SIZE,
        cursor: pageParam as string | undefined,
        service: filters.service,
        q: filters.q,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_cursor ?? undefined : undefined),
    refetchOnWindowFocus: true,
  });
}

export function useCorrectMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: correctMemory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['memoriesScroll'] }),
  });
}

// =============================================================================
// Lessons Learned (darwin_lessons)
// =============================================================================

export interface LessonsScrollFilters {
  channel?: 'external' | 'experience';
  q?: string;
}

export function useLessonsScroll(filters: LessonsScrollFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['lessonsScroll', filters],
    queryFn: ({ pageParam }) =>
      scrollLessons({
        limit: PAGE_SIZE,
        cursor: pageParam as string | undefined,
        channel: filters.channel,
        q: filters.q,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_cursor ?? undefined : undefined),
    refetchOnWindowFocus: true,
  });
}

export function useLessonById(lessonId: string | null) {
  return useQuery({
    queryKey: ['lesson', lessonId],
    queryFn: () => getLessonById(lessonId as string),
    enabled: !!lessonId,
  });
}

export function useCreateLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createLesson,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lessonsScroll'] }),
  });
}

export function useDeleteLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => deleteLesson(lessonId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lessonsScroll'] }),
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
      qc.invalidateQueries({ queryKey: ['memoriesScroll'] });
      qc.invalidateQueries({ queryKey: ['lessonsScroll'] });
    },
  });
}

// =============================================================================
// Knowledge Facts (darwin_knowledge)
// =============================================================================

export interface KnowledgeScrollFilters {
  scope?: import('../api/types').KnowledgeScope;
  service?: string;
  q?: string;
}

export function useKnowledgeScroll(filters: KnowledgeScrollFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['knowledgeScroll', filters],
    queryFn: ({ pageParam }) =>
      scrollKnowledge({
        limit: PAGE_SIZE,
        cursor: pageParam as string | undefined,
        scope: filters.scope,
        service: filters.service,
        q: filters.q,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_cursor ?? undefined : undefined),
    refetchOnWindowFocus: true,
  });
}

export function useCreateKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createKnowledge,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledgeScroll'] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledgeScroll'] }),
    onError: (err) => console.error('[knowledge] update failed:', err),
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteKnowledge(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledgeScroll'] }),
    onError: (err) => console.error('[knowledge] delete failed:', err),
  });
}
