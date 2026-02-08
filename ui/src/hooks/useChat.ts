// BlackBoard/ui/src/hooks/useChat.ts
/**
 * Chat hook -- sends messages via WebSocket for real-time processing.
 * Falls back to HTTP POST if WebSocket is not available.
 */
import { useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createChatEvent } from '../api/client';

/**
 * Chat hook that works with both WebSocket and HTTP.
 * When wsSend is provided, uses WebSocket. Otherwise falls back to HTTP.
 */
export function useChat(wsSend?: (data: object) => void) {
  const queryClient = useQueryClient();

  const httpMutation = useMutation({
    mutationFn: (params: { message: string; service?: string }) =>
      createChatEvent(params.message, params.service),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activeEvents'] });
    },
  });

  const sendMessage = useCallback((message: string, service?: string, image?: string) => {
    if (wsSend) {
      wsSend({ type: 'chat', message, service: service || 'general', ...(image ? { image } : {}) });
    } else {
      httpMutation.mutate({ message, service });
    }
  }, [wsSend, httpMutation]);

  return {
    sendMessage,
    isPending: httpMutation.isPending,
  };
}
