// BlackBoard/ui/src/utils/deferTimeline.ts
// @ai-rules:
// 1. [Pattern]: Pure helpers for defer countdown — no React imports.
// 2. [Constraint]: Timestamps are Unix seconds (API + conversation turns).
// 3. [Gotcha]: Fallback parses brain.defer thoughts when Redis defer_until is absent.

import type { ConversationTurn } from '../api/types';

export interface DeferTimeline {
  defer_until: number;
  defer_started_at: number;
}

export function formatDeferRemaining(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  if (s >= 3600) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return sec > 0 ? `${m}m ${sec}s` : `${m}m`;
  }
  return `${s}s`;
}

/** Last brain.defer turn → synthetic timeline when API omits Redis fields. */
export function inferDeferFromConversation(
  conversation: ConversationTurn[] | undefined,
): DeferTimeline | null {
  if (!conversation?.length) return null;
  for (let i = conversation.length - 1; i >= 0; i--) {
    const t = conversation[i];
    if (t.actor !== 'brain' || t.action !== 'defer') continue;
    const match = t.thoughts?.match(/Deferring event for (\d+)s/i);
    const delaySec = match ? Math.max(30, parseInt(match[1], 10)) : 60;
    const started = typeof t.timestamp === 'number' ? t.timestamp : Date.now() / 1000;
    return { defer_started_at: started, defer_until: started + delaySec };
  }
  return null;
}

export function resolveDeferTimeline(
  apiUntil?: number,
  apiStarted?: number,
  conversation?: ConversationTurn[],
): DeferTimeline | null {
  if (apiUntil != null && Number.isFinite(apiUntil)) {
    let started = apiStarted;
    if (started == null || !Number.isFinite(started) || started > apiUntil) {
      started = apiUntil - 60;
    }
    return { defer_until: apiUntil, defer_started_at: started };
  }
  return inferDeferFromConversation(conversation);
}

export function computeDeferProgress(
  timeline: DeferTimeline,
  nowSec: number,
): { ratio: number; remainingSec: number; expired: boolean; totalSec: number } {
  const { defer_until: end, defer_started_at: start } = timeline;
  const totalSec = Math.max(1, end - start);
  const remainingSec = end - nowSec;
  const expired = remainingSec <= 0;
  const ratio = expired ? 0 : Math.min(1, Math.max(0, remainingSec / totalSec));
  return { ratio, remainingSec, expired, totalSec };
}
