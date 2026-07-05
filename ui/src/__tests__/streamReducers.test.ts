// BlackBoard/ui/src/__tests__/streamReducers.test.ts
import { describe, it, expect } from 'vitest';
import {
  buildStreamKey, applyProgress, applyTurn,
  removeStreamsForEvent, computeGCDeletes, computeGridCols,
  MAX_BUFFER, type Streams,
} from '../utils/streamReducers';

describe('buildStreamKey', () => {
  it('produces actor:eventId', () => {
    expect(buildStreamKey('sysadmin', 'evt-abc123')).toBe('sysadmin:evt-abc123');
  });
});

describe('applyProgress', () => {
  it('creates new stream with correct fields', () => {
    const result = applyProgress({}, 'architect', 'evt-1', 'hello');
    expect(result['architect:evt-1']).toEqual({
      messages: ['hello'],
      actor: 'architect',
      eventId: 'evt-1',
      isActive: true,
    });
  });

  it('appends to existing stream', () => {
    const prev: Streams = {
      'dev:evt-2': { messages: ['line1'], actor: 'dev', eventId: 'evt-2', isActive: true },
    };
    const result = applyProgress(prev, 'dev', 'evt-2', 'line2');
    expect(result['dev:evt-2'].messages).toEqual(['line1', 'line2']);
    expect(result['dev:evt-2'].isActive).toBe(true);
  });

  it('caps at MAX_BUFFER', () => {
    const messages = Array.from({ length: MAX_BUFFER }, (_, i) => `msg-${i}`);
    const prev: Streams = {
      'a:e': { messages, actor: 'a', eventId: 'e', isActive: true },
    };
    const result = applyProgress(prev, 'a', 'e', 'overflow');
    expect(result['a:e'].messages).toHaveLength(MAX_BUFFER);
    expect(result['a:e'].messages[MAX_BUFFER - 1]).toBe('overflow');
    expect(result['a:e'].messages[0]).toBe('msg-1');
  });
});

describe('applyTurn', () => {
  it('marks existing stream inactive', () => {
    const prev: Streams = {
      'qe:evt-3': { messages: ['test output'], actor: 'qe', eventId: 'evt-3', isActive: true },
    };
    const result = applyTurn(prev, 'qe', 'evt-3');
    expect(result['qe:evt-3'].isActive).toBe(false);
    expect(result['qe:evt-3'].messages).toEqual(['test output']);
  });

  it('creates inactive placeholder for missing key', () => {
    const result = applyTurn({}, 'dev', 'evt-4');
    expect(result['dev:evt-4']).toEqual({
      messages: [],
      actor: 'dev',
      eventId: 'evt-4',
      isActive: false,
    });
  });
});

describe('removeStreamsForEvent', () => {
  const base: Streams = {
    'a:evt-1': { messages: ['x'], actor: 'a', eventId: 'evt-1', isActive: true },
    'b:evt-1': { messages: ['y'], actor: 'b', eventId: 'evt-1', isActive: false },
    'c:evt-2': { messages: ['z'], actor: 'c', eventId: 'evt-2', isActive: true },
  };

  it('removes all streams for closed event', () => {
    const result = removeStreamsForEvent(base, 'evt-1');
    expect(Object.keys(result)).toEqual(['c:evt-2']);
  });

  it('preserves streams for other events', () => {
    const result = removeStreamsForEvent(base, 'evt-1');
    expect(result['c:evt-2']).toEqual(base['c:evt-2']);
  });

  it('returns same reference when no match', () => {
    const result = removeStreamsForEvent(base, 'evt-999');
    expect(result).toBe(base);
  });
});

describe('computeGCDeletes', () => {
  const streams: Streams = {
    'a:evt-1': { messages: ['x'], actor: 'a', eventId: 'evt-1', isActive: true },
    'b:evt-2': { messages: ['y'], actor: 'b', eventId: 'evt-2', isActive: true },
    'c:evt-3': { messages: ['z'], actor: 'c', eventId: 'evt-3', isActive: false },
  };

  it('first pass marks only (toDelete empty)', () => {
    const activeIds = new Set(['evt-1']);
    const { toDelete, nextCandidates } = computeGCDeletes(streams, activeIds, new Set());
    expect(toDelete).toEqual([]);
    expect(nextCandidates.has('b:evt-2')).toBe(true);
    expect(nextCandidates.has('c:evt-3')).toBe(true);
  });

  it('second pass deletes previously marked streams', () => {
    const activeIds = new Set(['evt-1']);
    const staleCandidates = new Set(['b:evt-2', 'c:evt-3']);
    const { toDelete } = computeGCDeletes(streams, activeIds, staleCandidates);
    expect(toDelete).toContain('b:evt-2');
    expect(toDelete).toContain('c:evt-3');
  });

  it('resets mark when event becomes active again', () => {
    const activeIds = new Set(['evt-1', 'evt-2']);
    const staleCandidates = new Set(['b:evt-2', 'c:evt-3']);
    const { toDelete, nextCandidates } = computeGCDeletes(streams, activeIds, staleCandidates);
    expect(toDelete).toEqual(['c:evt-3']);
    expect(nextCandidates.has('b:evt-2')).toBe(false);
  });
});

describe('computeGridCols', () => {
  it.each([
    [0, 1],
    [1, 1],
    [2, 2],
    [3, 2],
    [4, 2],
    [5, 3],
    [9, 3],
    [10, 4],
  ])('count=%d → cols=%d', (count, expected) => {
    expect(computeGridCols(count)).toBe(expected);
  });
});
