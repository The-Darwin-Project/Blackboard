import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, render, screen, fireEvent, cleanup } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ActiveEvent } from '../api/types';

type WSHandler = (msg: Record<string, unknown>) => void;
let wsHandler: WSHandler | null = null;
const mockSend = vi.fn();

vi.mock('./WebSocketContext', () => ({
  useWSMessage: (h: WSHandler) => { wsHandler = h; },
  useWSReconnect: () => {},
  useWSConnection: () => ({ connected: true, reconnecting: false, send: mockSend }),
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
// Avoid a live fetch (which would overwrite the seeded cache); keep the real invalidation/patch helpers.
vi.mock('../hooks/useQueue', async (orig) => {
  const real = await orig<typeof import('../hooks/useQueue')>();
  return { ...real, useActiveEvents: () => ({ data: [] }) };
});

import { OpsControlProvider, useOpsControl } from './OpsStateContext';

const KEY = ['activeEvents'];
const baseEvent = {
  id: 'e1',
  source: 'chat',
  service: 'svc',
  status: 'active',
  reason: '',
  turns: 0,
  created: '',
  evidence: { display_text: 'x', source_type: 't', domain: 'disorder', severity: 'info' },
} as unknown as ActiveEvent;

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

describe('OpsControlProvider domain_updated / severity_updated', () => {
  let qc: QueryClient;

  beforeEach(() => {
    qc = new QueryClient();
    qc.setQueryData(KEY, [baseEvent]);
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, createElement(OpsControlProvider, null, children));
    renderHook(() => null, { wrapper });
  });

  const evidence = () => qc.getQueryData<ActiveEvent[]>(KEY)![0].evidence;

  it('domain_updated patches brain_domain and preserves base domain', () => {
    act(() => wsHandler!({ type: 'domain_updated', event_id: 'e1', domain: 'complex' }));
    expect(evidence().brain_domain).toBe('complex');
    expect(evidence().domain).toBe('disorder');
    expect(evidence().display_text).toBe('x');
  });

  it('severity_updated patches brain_severity and preserves base severity', () => {
    act(() => wsHandler!({ type: 'severity_updated', event_id: 'e1', severity: 'critical' }));
    expect(evidence().brain_severity).toBe('critical');
    expect(evidence().severity).toBe('info');
  });

  it.each([undefined, '', 42, null])('domain_updated ignores invalid domain %j', (domain) => {
    act(() => wsHandler!({ type: 'domain_updated', event_id: 'e1', domain }));
    expect(evidence().brain_domain).toBeUndefined();
    expect(evidence().domain).toBe('disorder');
  });

  it.each([undefined, '', 'bogus', 7])('severity_updated ignores invalid severity %j', (severity) => {
    act(() => wsHandler!({ type: 'severity_updated', event_id: 'e1', severity }));
    expect(evidence().brain_severity).toBeUndefined();
    expect(evidence().severity).toBe('info');
  });

  it('ignores messages without an event_id', () => {
    act(() => wsHandler!({ type: 'domain_updated', domain: 'clear' }));
    expect(evidence().brain_domain).toBeUndefined();
  });
});

describe('OpsControlProvider event_closed selection lifecycle', () => {
  const STORAGE_KEY = 'darwin:selectedEventId';

  const setup = (path: string, selected: string | null = 'evt-1') => {
    window.history.pushState({}, '', path);
    sessionStorage.clear();
    if (selected) sessionStorage.setItem(STORAGE_KEY, selected);
    const qc = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, createElement(OpsControlProvider, null, children));
    return renderHook(() => useOpsControl(), { wrapper });
  };

  afterEach(() => {
    window.history.pushState({}, '', '/');
    sessionStorage.clear();
  });

  it('on /workspace/<id>: keeps in-memory selection but clears sessionStorage', () => {
    const { result } = setup('/workspace/evt-1');
    expect(result.current.selectedEventId).toBe('evt-1');
    act(() => wsHandler!({ type: 'event_closed', event_id: 'evt-1' }));
    expect(result.current.selectedEventId).toBe('evt-1');
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('on exactly /workspace: keeps in-memory selection but clears sessionStorage', () => {
    const { result } = setup('/workspace');
    act(() => wsHandler!({ type: 'event_closed', event_id: 'evt-1' }));
    expect(result.current.selectedEventId).toBe('evt-1');
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('on /: clears both in-memory selection and sessionStorage', () => {
    const { result } = setup('/');
    act(() => wsHandler!({ type: 'event_closed', event_id: 'evt-1' }));
    expect(result.current.selectedEventId).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('on /workspaces-other (prefix-only match): clears both', () => {
    const { result } = setup('/workspaces-other');
    act(() => wsHandler!({ type: 'event_closed', event_id: 'evt-1' }));
    expect(result.current.selectedEventId).toBeNull();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it.each(['/', '/workspace/evt-1'])('on %s: a non-selected event closing preserves both', (path) => {
    const { result } = setup(path);
    act(() => wsHandler!({ type: 'event_closed', event_id: 'evt-other' }));
    expect(result.current.selectedEventId).toBe('evt-1');
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe('evt-1');
  });
});

describe('OpsControlProvider approval error banner', () => {
  beforeEach(() => { mockSend.mockClear(); });
  afterEach(() => { cleanup(); });

  const mountProvider = () => {
    const qc = new QueryClient();
    return render(
      createElement(QueryClientProvider, { client: qc },
        createElement(OpsControlProvider, null, createElement('div', null, 'child')),
      ),
    );
  };

  it('renders sha_drift alert with Confirm New SHA action and clears on confirm', () => {
    mountProvider();
    act(() => wsHandler!({
      type: 'error', kind: 'sha_drift', event_id: 'evt-d', live_sha: 'deadbeef1', message: 'HEAD SHA drifted',
    }));
    expect(screen.getByRole('alert').textContent).toContain('HEAD SHA drifted');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm New SHA' }));
    expect(mockSend).toHaveBeenCalledWith({ type: 'approve', event_id: 'evt-d', expected_sha: 'deadbeef1' });
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('renders closed alert without Confirm New SHA and dismisses via Dismiss button', () => {
    mountProvider();
    act(() => wsHandler!({
      type: 'error', kind: 'closed', event_id: 'evt-c', message: 'Event is already closed',
    }));
    expect(screen.getByRole('alert').textContent).toContain('Event is already closed');
    expect(screen.queryByRole('button', { name: 'Confirm New SHA' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('OpsControlProvider headhunter query invalidation (T-16)', () => {
  let qc: QueryClient;
  let invalidateSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    qc = new QueryClient();
    invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: qc }, createElement(OpsControlProvider, null, children));
    renderHook(() => null, { wrapper });
  });

  afterEach(() => {
    invalidateSpy.mockRestore();
    cleanup();
  });

  it('Given OpsControlProvider mounted, When WS event_created arrives, Then invalidates headhunterPending and headhunterStatus queries', () => {
    invalidateSpy.mockClear();
    act(() => wsHandler!({ type: 'event_created', event_id: 'evt-hh-new' }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['headhunterPending'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['headhunterStatus'] });
  });

  it('Given OpsControlProvider mounted, When WS event_status_changed arrives, Then invalidates headhunterPending and headhunterStatus queries', () => {
    invalidateSpy.mockClear();
    act(() => wsHandler!({ type: 'event_status_changed', event_id: 'evt-hh-park', status: 'waiting_approval' }));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['headhunterPending'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['headhunterStatus'] });
  });
});

describe('OpsControlProvider headhunter invalidation coalescing (M10)', () => {
  it('Given a 5-message WS event burst, When processed within 1500ms, Then fires 1 leading invalidation and 1 coalesced trailing invalidation after 1500ms', () => {
    vi.useFakeTimers();
    const qc = new QueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    try {
      const wrapper = ({ children }: { children: ReactNode }) =>
        createElement(QueryClientProvider, { client: qc }, createElement(OpsControlProvider, null, children));
      renderHook(() => null, { wrapper });

      invalidateSpy.mockClear();

      act(() => {
        wsHandler!({ type: 'event_created', event_id: 'evt-burst-1' });
        wsHandler!({ type: 'event_status_changed', event_id: 'evt-burst-1', status: 'active' });
        wsHandler!({ type: 'event_created', event_id: 'evt-burst-2' });
        wsHandler!({ type: 'event_status_changed', event_id: 'evt-burst-2', status: 'waiting_approval' });
        wsHandler!({ type: 'event_closed', event_id: 'evt-burst-1' });
      });

      const pendingCallsBefore = () =>
        invalidateSpy.mock.calls.filter(([arg]) => (arg as { queryKey?: unknown[] })?.queryKey?.[0] === 'headhunterPending').length;
      const statusCallsBefore = () =>
        invalidateSpy.mock.calls.filter(([arg]) => (arg as { queryKey?: unknown[] })?.queryKey?.[0] === 'headhunterStatus').length;

      expect(pendingCallsBefore()).toBe(1);
      expect(statusCallsBefore()).toBe(1);

      act(() => {
        vi.advanceTimersByTime(1499);
      });
      expect(pendingCallsBefore()).toBe(1);
      expect(statusCallsBefore()).toBe(1);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(pendingCallsBefore()).toBe(2);
      expect(statusCallsBefore()).toBe(2);
    } finally {
      invalidateSpy.mockRestore();
      cleanup();
      vi.useRealTimers();
    }
  });
});
