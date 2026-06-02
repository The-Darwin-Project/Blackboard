// BlackBoard/ui/src/__tests__/deferTimeline.test.ts
import { describe, expect, it } from 'vitest';
import {
  computeDeferProgress,
  formatDeferRemaining,
  inferDeferFromConversation,
  resolveDeferTimeline,
} from '../utils/deferTimeline';

describe('deferTimeline', () => {
  it('formats remaining time', () => {
    expect(formatDeferRemaining(45)).toBe('45s');
    expect(formatDeferRemaining(125)).toBe('2m 5s');
  });

  it('infers timeline from defer turn', () => {
    const t = inferDeferFromConversation([
      { turn: 1, actor: 'brain', action: 'defer', thoughts: 'Deferring event for 300s: pipeline', timestamp: 1000 },
    ]);
    expect(t).toEqual({ defer_started_at: 1000, defer_until: 1300 });
  });

  it('computes shrinking ratio', () => {
    const timeline = { defer_started_at: 0, defer_until: 100 };
    const mid = computeDeferProgress(timeline, 50);
    expect(mid.ratio).toBeCloseTo(0.5);
    const done = computeDeferProgress(timeline, 100);
    expect(done.expired).toBe(true);
    expect(done.ratio).toBe(0);
  });

  it('prefers API timestamps over conversation', () => {
    const t = resolveDeferTimeline(2000, 1000, [
      { turn: 1, actor: 'brain', action: 'defer', thoughts: 'Deferring event for 60s: x', timestamp: 500 },
    ]);
    expect(t?.defer_until).toBe(2000);
    expect(t?.defer_started_at).toBe(1000);
  });

  it('clamps defer_started_at when apiStarted > apiUntil', () => {
    const t = resolveDeferTimeline(1000, 2000);
    expect(t?.defer_until).toBe(1000);
    expect(t?.defer_started_at).toBe(940);
  });

  it('falls back to 60s when thoughts do not match regex', () => {
    const t = inferDeferFromConversation([
      { turn: 1, actor: 'brain', action: 'defer', thoughts: 'Some unknown format', timestamp: 500 },
    ]);
    expect(t).toEqual({ defer_started_at: 500, defer_until: 560 });
  });

  it('returns null when conversation has no defer turns', () => {
    const t = inferDeferFromConversation([
      { turn: 1, actor: 'brain', action: 'triage', thoughts: 'triaging', timestamp: 100 },
    ]);
    expect(t).toBeNull();
  });
});
