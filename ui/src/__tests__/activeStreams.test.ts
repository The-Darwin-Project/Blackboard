// BlackBoard/ui/src/__tests__/activeStreams.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

type MessageHandler = (msg: Record<string, unknown>) => void;
type ReconnectHandler = () => void;

let capturedWSHandler: MessageHandler | null = null;
let capturedReconnectHandler: ReconnectHandler | null = null;

const mockInvalidateActive = vi.fn();
const mockInvalidateEvent = vi.fn();
const mockInvalidateClosed = vi.fn();

vi.mock('../contexts/WebSocketContext', () => ({
  useWSMessage: (handler: MessageHandler) => { capturedWSHandler = handler; },
  useWSReconnect: (handler: ReconnectHandler) => { capturedReconnectHandler = handler; },
  useWSConnection: () => ({ connected: true, reconnecting: false, send: vi.fn() }),
}));

vi.mock('../hooks/useQueue', () => ({
  useQueueInvalidation: () => ({
    invalidateActive: mockInvalidateActive,
    invalidateEvent: mockInvalidateEvent,
    invalidateAll: vi.fn(),
    invalidateClosed: mockInvalidateClosed,
    invalidateHeadhunter: vi.fn(),
    optimisticRemoveEvent: vi.fn(),
    optimisticPatchEvent: vi.fn(),
  }),
  useActiveEvents: () => ({ data: [{ id: 'evt-1' }, { id: 'evt-2' }] }),
  useWaitingApprovalEvents: () => ({ data: [] }),
  useHeadhunterPending: () => ({ data: null }),
}));

vi.mock('../hooks/useKargo', () => ({
  useKargoStages: () => ({ data: [] }),
  useKargoStagesInvalidation: () => ({ setKargoStages: vi.fn(), invalidateKargoStages: vi.fn() }),
}));

vi.mock('../api/client', () => ({
  getAgents: vi.fn().mockResolvedValue([]),
  getActiveEvents: vi.fn().mockResolvedValue([]),
  getWSAuthFailureCallback: () => () => {},
}));

import { ActiveStreamsProvider, useActiveStreams } from '../contexts/ActiveStreamsContext';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider, { client: queryClient },
      createElement(ActiveStreamsProvider, null, children),
    );
  };
}

beforeEach(() => {
  capturedWSHandler = null;
  capturedReconnectHandler = null;
  mockInvalidateActive.mockClear();
  mockInvalidateEvent.mockClear();
  mockInvalidateClosed.mockClear();
});

describe('ActiveStreamsProvider', () => {
  it('progress message creates stream', () => {
    const { result } = renderHook(() => useActiveStreams(), { wrapper: createWrapper() });
    expect(capturedWSHandler).not.toBeNull();

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'architect', event_id: 'evt-1', message: 'Building plan...' });
    });

    expect(result.current.activeStreams['architect:evt-1']).toEqual({
      messages: ['Building plan...'],
      actor: 'architect',
      eventId: 'evt-1',
      isActive: true,
    });
  });

  it('late progress after event_closed is ignored', () => {
    const { result } = renderHook(() => useActiveStreams(), { wrapper: createWrapper() });

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'dev', event_id: 'evt-x', message: 'line1' });
    });
    expect(result.current.activeStreams['dev:evt-x']).toBeDefined();

    act(() => {
      capturedWSHandler!({ type: 'event_closed', event_id: 'evt-x' });
    });
    expect(result.current.activeStreams['dev:evt-x']).toBeUndefined();

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'dev', event_id: 'evt-x', message: 'late' });
    });
    expect(result.current.activeStreams['dev:evt-x']).toBeUndefined();
  });

  it('turn marks stream inactive and fires invalidation', () => {
    const { result } = renderHook(() => useActiveStreams(), { wrapper: createWrapper() });

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'qe', event_id: 'evt-2', message: 'testing' });
    });
    expect(result.current.activeStreams['qe:evt-2'].isActive).toBe(true);

    act(() => {
      capturedWSHandler!({ type: 'turn', turn: { actor: 'qe' }, event_id: 'evt-2' });
    });
    expect(result.current.activeStreams['qe:evt-2'].isActive).toBe(false);
    expect(mockInvalidateActive).toHaveBeenCalled();
    expect(mockInvalidateEvent).toHaveBeenCalledWith('evt-2');
  });

  it('event_closed removes all streams for that event', () => {
    const { result } = renderHook(() => useActiveStreams(), { wrapper: createWrapper() });

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'a', event_id: 'evt-3', message: 'm1' });
      capturedWSHandler!({ type: 'progress', actor: 'b', event_id: 'evt-3', message: 'm2' });
      capturedWSHandler!({ type: 'progress', actor: 'c', event_id: 'evt-4', message: 'm3' });
    });
    expect(Object.keys(result.current.activeStreams)).toHaveLength(3);

    act(() => {
      capturedWSHandler!({ type: 'event_closed', event_id: 'evt-3' });
    });
    expect(Object.keys(result.current.activeStreams)).toHaveLength(1);
    expect(result.current.activeStreams['c:evt-4']).toBeDefined();
    expect(mockInvalidateActive).toHaveBeenCalled();
    expect(mockInvalidateClosed).toHaveBeenCalled();
  });

  it('useWSReconnect clears recentlyClosedRef', () => {
    const { result } = renderHook(() => useActiveStreams(), { wrapper: createWrapper() });

    act(() => {
      capturedWSHandler!({ type: 'event_closed', event_id: 'evt-5' });
    });

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'x', event_id: 'evt-5', message: 'should be blocked' });
    });
    expect(result.current.activeStreams['x:evt-5']).toBeUndefined();

    act(() => {
      capturedReconnectHandler!();
    });

    act(() => {
      capturedWSHandler!({ type: 'progress', actor: 'x', event_id: 'evt-5', message: 'should work now' });
    });
    expect(result.current.activeStreams['x:evt-5']).toBeDefined();
  });
});
