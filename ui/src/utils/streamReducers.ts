// BlackBoard/ui/src/utils/streamReducers.ts
// @ai-rules:
// 1. [Constraint]: Pure functions only — no React, no side effects, no external state.
// 2. [Pattern]: All functions return new objects (immutable updates for React state).
// 3. [Pattern]: Same-reference return when no mutation needed (avoids unnecessary re-renders).
// 4. [Gotcha]: computeGCDeletes uses two-pass mark-and-sweep — first call marks, second deletes.

export const MAX_BUFFER = 100;

export interface ActiveStream {
  messages: string[];
  actor: string;
  eventId: string;
  isActive: boolean;
}

export type Streams = Record<string, ActiveStream>;

export function buildStreamKey(actor: string, eventId: string): string {
  return `${actor}:${eventId}`;
}

export function applyProgress(prev: Streams, actor: string, eventId: string, message: string): Streams {
  const key = buildStreamKey(actor, eventId);
  const current = prev[key];
  const messages = [...(current?.messages || []), message].slice(-MAX_BUFFER);
  return { ...prev, [key]: { messages, actor, eventId, isActive: true } };
}

export function applyTurn(prev: Streams, actor: string, eventId: string): Streams {
  const key = buildStreamKey(actor, eventId);
  const current = prev[key];
  if (!current) {
    return { ...prev, [key]: { messages: [], actor, eventId, isActive: false } };
  }
  if (!current.isActive) return prev;
  return { ...prev, [key]: { ...current, isActive: false } };
}

export function removeStreamsForEvent(prev: Streams, closedEventId: string): Streams {
  const keys = Object.keys(prev);
  const toRemove = keys.filter(k => prev[k].eventId === closedEventId);
  if (toRemove.length === 0) return prev;
  const next = { ...prev };
  for (const k of toRemove) delete next[k];
  return next;
}

export function computeGCDeletes(
  streams: Streams,
  activeEventIds: Set<string>,
  staleCandidates: Set<string>,
): { toDelete: string[]; nextCandidates: Set<string> } {
  const currentKeys = Object.keys(streams);
  const nowStale = currentKeys.filter(k => {
    const stream = streams[k];
    return stream && !activeEventIds.has(stream.eventId);
  });
  const toDelete = nowStale.filter(k => staleCandidates.has(k));
  const nextCandidates = new Set(nowStale);
  return { toDelete, nextCandidates };
}

export function computeGridCols(count: number): number {
  if (count <= 1) return 1;
  if (count <= 2) return 2;
  return Math.ceil(Math.sqrt(count));
}
