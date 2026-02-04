// BlackBoard/ui/src/hooks/useChat.ts
/**
 * TanStack Query mutation hook for chat.
 * Sends messages to /chat/ endpoint.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendChatMessage } from '../api/client';

/**
 * Hook for sending chat messages to the Architect.
 */
export function useChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (message: string) => sendChatMessage(message),
    onSuccess: () => {
      // Invalidate plans and events as chat may create new plans
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });
}
