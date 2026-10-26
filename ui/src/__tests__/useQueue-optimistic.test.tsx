import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useQueueInvalidation } from '../hooks/useQueue';
import type { ActiveEvent } from '../api/types';

const KEY = ['activeEvents'];

const makeEvent = (over: Record<string, unknown> = {}): ActiveEvent =>
  ({
    id: 'e1',
    source: 'chat',
    service: 'svc',
    status: 'active',
    reason: '',
    turns: 0,
    created: '',
    evidence: { display_text: 'x', source_type: 't', domain: 'clear', severity: 'info' },
    ...over,
  }) as unknown as ActiveEvent;

function setup(seed?: ActiveEvent[]) {
  const qc = new QueryClient();
  if (seed !== undefined) qc.setQueryData(KEY, seed);
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children);
  const { result } = renderHook(() => useQueueInvalidation(), { wrapper });
  return { qc, api: result.current };
}

describe('optimisticPatchEvent', () => {
  it('deep-merges partial evidence, preserving sibling fields and other events', () => {
    const other = makeEvent({ id: 'e2' });
    const { qc, api } = setup([makeEvent(), other]);
    api.optimisticPatchEvent('e1', { evidence: { brain_domain: 'complex' } });
    const data = qc.getQueryData<ActiveEvent[]>(KEY)!;
    expect(data[0].evidence).toEqual({
      display_text: 'x', source_type: 't', domain: 'clear', severity: 'info', brain_domain: 'complex',
    });
    expect(data[1]).toEqual(other);
  });

  it('leaves evidence untouched for non-evidence patches', () => {
    const { qc, api } = setup([makeEvent()]);
    api.optimisticPatchEvent('e1', { status: 'deferred', defer_until: 5 });
    const [evt] = qc.getQueryData<ActiveEvent[]>(KEY)!;
    expect(evt.status).toBe('deferred');
    expect(evt.defer_until).toBe(5);
    expect(evt.evidence.domain).toBe('clear');
  });

  it('applies an evidence patch when the cached event has no evidence', () => {
    const { qc, api } = setup([makeEvent({ evidence: undefined })]);
    api.optimisticPatchEvent('e1', { evidence: { brain_domain: 'complex' } });
    expect(qc.getQueryData<ActiveEvent[]>(KEY)![0].evidence).toEqual({ brain_domain: 'complex' });
  });

  it('keeps an unloaded (undefined) cache undefined', () => {
    const { qc, api } = setup();
    api.optimisticPatchEvent('e1', { status: 'deferred' });
    expect(qc.getQueryData(KEY)).toBeUndefined();
  });

  it('is a no-op for an unknown event id', () => {
    const { qc, api } = setup([makeEvent()]);
    api.optimisticPatchEvent('nope', { evidence: { brain_domain: 'complex' } });
    expect(qc.getQueryData<ActiveEvent[]>(KEY)).toEqual([makeEvent()]);
  });
});

describe('optimisticRemoveEvent', () => {
  it('removes the event from a loaded cache', () => {
    const { qc, api } = setup([makeEvent(), makeEvent({ id: 'e2' })]);
    api.optimisticRemoveEvent('e1');
    expect(qc.getQueryData<ActiveEvent[]>(KEY)!.map((e) => e.id)).toEqual(['e2']);
  });

  it('keeps an unloaded (undefined) cache undefined', () => {
    const { qc, api } = setup();
    api.optimisticRemoveEvent('e1');
    expect(qc.getQueryData(KEY)).toBeUndefined();
  });
});
