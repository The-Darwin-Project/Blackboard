// BlackBoard/ui/src/hooks/useObservationsMutations.ts
// @ai-rules:
// 1. [Pattern]: useMutation hooks wrapping client.ts functions. Invalidates ['observations'] on success.
// 2. [Constraint]: Import API wrappers from client.ts — fetchApi is module-private.
/**
 * Mutation hooks for observation management (delete, rename, bulk-delete).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  deleteObservation,
  renameObservation,
  bulkDeleteObservations,
} from '../api/client';

export function useDeleteObservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteObservation(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['observations'] }),
  });
}

export function useRenameObservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, newName }: { name: string; newName: string }) =>
      renameObservation(name, newName),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['observations'] }),
  });
}

export function useBulkDeleteObservations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (names: string[]) => bulkDeleteObservations(names),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['observations'] }),
  });
}
