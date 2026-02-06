// BlackBoard/ui/src/hooks/useChat.ts
/**
 * TanStack Query mutation hook for creating chat events.
 * Sends messages to /chat/ which creates an event in the queue.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createChatEvent } from '../api/client';

export function useChat() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (params: { message: string; service?: string }) =>
      createChatEvent(params.message, params.service),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeEvents'] });
    },
  });

  return mutation;
}
