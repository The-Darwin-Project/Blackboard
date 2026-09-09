// BlackBoard/ui/src/hooks/useChat.test.ts
// @ai-rules:
// 1. [Constraint]: Covers the evt-dc56392b regression (code-review HIGH finding: "missing UI
//    regression test") -- the REST-fallback mutation must thread eventId through to
//    createChatEvent so replies to an active event don't spawn a new one when the WS is down.
import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { useChat } from './useChat';

vi.mock('../api/client', () => ({
  createChatEvent: vi.fn(),
}));

import { createChatEvent } from '../api/client';

const mockCreateChatEvent = vi.mocked(createChatEvent);

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useChat REST fallback (no wsSend)', () => {
  it('threads eventId through to createChatEvent when replying to an active event', async () => {
    mockCreateChatEvent.mockResolvedValue({ event_id: 'evt-active01', status: 'appended' });
    const { result } = renderHook(() => useChat(undefined), { wrapper });

    act(() => {
      result.current.sendMessage('reply here', 'general', undefined, 'evt-active01');
    });

    await waitFor(() => expect(mockCreateChatEvent).toHaveBeenCalledTimes(1));
    expect(mockCreateChatEvent).toHaveBeenCalledWith('reply here', 'general', 'evt-active01');
  });

  it('omits eventId when none is selected (creates a new event, unchanged behavior)', async () => {
    mockCreateChatEvent.mockResolvedValue({ event_id: 'evt-new0001', status: 'created' });
    const { result } = renderHook(() => useChat(undefined), { wrapper });

    act(() => {
      result.current.sendMessage('ask the brain', 'general', undefined, undefined);
    });

    await waitFor(() => expect(mockCreateChatEvent).toHaveBeenCalledTimes(1));
    expect(mockCreateChatEvent).toHaveBeenCalledWith('ask the brain', 'general', undefined);
  });

  it('does not call createChatEvent when a WS sender is available (uses WS instead)', () => {
    const wsSend = vi.fn();
    const { result } = renderHook(() => useChat(wsSend), { wrapper });

    act(() => {
      result.current.sendMessage('hello', 'general');
    });

    expect(wsSend).toHaveBeenCalledTimes(1);
    expect(mockCreateChatEvent).not.toHaveBeenCalled();
  });
});
