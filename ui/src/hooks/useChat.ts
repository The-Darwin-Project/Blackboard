// BlackBoard/ui/src/hooks/useChat.ts
/**
 * TanStack Query mutation hook for chat with conversation support.
 * Sends messages to /chat/ endpoint and tracks conversation state.
 */
import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendChatMessage } from '../api/client';

/**
 * Hook for sending chat messages to the Architect with conversation tracking.
 * 
 * Maintains conversation_id state across multiple messages for multi-turn context.
 */
export function useChat() {
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (message: string) => sendChatMessage(message, conversationId),
    onSuccess: (data) => {
      // Update conversation ID for follow-up messages
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }
      // Invalidate plans and events as chat may create new plans
      queryClient.invalidateQueries({ queryKey: ['plans'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
  });

  // Reset conversation to start fresh
  const resetConversation = useCallback(() => {
    setConversationId(null);
  }, []);

  return {
    ...mutation,
    conversationId,
    resetConversation,
  };
}
