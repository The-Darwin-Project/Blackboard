// BlackBoard/ui/src/hooks/useDeferCountdown.ts
// @ai-rules:
// 1. [Pattern]: 1s tick while defer is active; stops when expired or no timeline.
// 2. [Constraint]: Accepts optional conversation for API-less fallback.

import { useEffect, useMemo, useState } from 'react';
import type { ConversationTurn } from '../api/types';
import {
  computeDeferProgress,
  formatDeferRemaining,
  resolveDeferTimeline,
  type DeferTimeline,
} from '../utils/deferTimeline';

export interface DeferCountdownState {
  timeline: DeferTimeline | null;
  ratio: number;
  remainingLabel: string;
  expired: boolean;
  ariaValueNow: number;
  ariaValueMax: number;
}

export function useDeferCountdown(
  deferUntil?: number,
  deferStartedAt?: number,
  conversation?: ConversationTurn[],
  enabled = true,
): DeferCountdownState {
  const timeline = useMemo(
    () => (enabled ? resolveDeferTimeline(deferUntil, deferStartedAt, conversation) : null),
    [enabled, deferUntil, deferStartedAt, conversation],
  );

  const [nowSec, setNowSec] = useState(() => Date.now() / 1000);

  useEffect(() => {
    if (!timeline) return;
    setNowSec(Date.now() / 1000);
    const id = window.setInterval(() => setNowSec(Date.now() / 1000), 1000);
    return () => window.clearInterval(id);
  }, [timeline?.defer_until, timeline?.defer_started_at]);

  return useMemo(() => {
    if (!timeline) {
      return {
        timeline: null,
        ratio: 0,
        remainingLabel: '',
        expired: false,
        ariaValueNow: 0,
        ariaValueMax: 100,
      };
    }
    const { ratio, remainingSec, expired } = computeDeferProgress(timeline, nowSec);
    return {
      timeline,
      ratio,
      remainingLabel: expired ? 'Waking up' : formatDeferRemaining(remainingSec),
      expired,
      ariaValueNow: Math.round(ratio * 100),
      ariaValueMax: 100,
    };
  }, [timeline, nowSec]);
}
