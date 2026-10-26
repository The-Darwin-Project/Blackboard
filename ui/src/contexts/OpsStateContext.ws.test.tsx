import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ActiveEvent } from '../api/types';

type WSHandler = (msg: Record<string, unknown>) => void;
let wsHandler: WSHandler | null = null;

vi.mock('./WebSocketContext', () => ({
  useWSMessage: (h: WSHandler) => { wsHandler = h; },
  useWSReconnect: () => {},
  useWSConnection: () => ({ connected: true, reconnecting: false, send: vi.fn() }),
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

import { OpsControlProvider } from './OpsStateContext';

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
