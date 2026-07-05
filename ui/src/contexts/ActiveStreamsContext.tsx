// BlackBoard/ui/src/contexts/ActiveStreamsContext.tsx
// @ai-rules:
// 1. [Pattern]: Owns ONLY activeStreams state. High-frequency WS updates (40Hz) isolated here.
// 2. [Pattern]: recentlyClosedRef FIFO cap=50 — late progress after event_closed discarded.
// 3. [Pattern]: Mark-and-sweep GC (60s interval, staleCandidatesRef). Two consecutive misses → delete.
// 4. [Pattern]: useWSReconnect clears recentlyClosedRef only. Query invalidation owned by OpsControl.
// 5. [Constraint]: Must be nested inside WebSocketProvider AND OpsControlProvider (reads activeEvents).
// 6. [Pattern]: Both this and OpsControl call useActiveEvents() — React Query deduplicates via same key.
import { createContext, useContext, useState, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useWSMessage, useWSReconnect } from './WebSocketContext';
import { useQueueInvalidation, useActiveEvents } from '../hooks/useQueue';
import {
  type Streams, type ActiveStream,
  applyProgress, applyTurn, removeStreamsForEvent, computeGCDeletes,
} from '../utils/streamReducers';

export type { ActiveStream };

interface ActiveStreamsState {
  activeStreams: Streams;
}

const ActiveStreamsContext = createContext<ActiveStreamsState | null>(null);

export function useActiveStreams(): ActiveStreamsState {
  const ctx = useContext(ActiveStreamsContext);
  if (!ctx) throw new Error('useActiveStreams must be used within ActiveStreamsProvider');
  return ctx;
}

export function ActiveStreamsProvider({ children }: { children: ReactNode }) {
  const [activeStreams, setActiveStreams] = useState<Streams>({});
  const { data: activeEvents } = useActiveEvents();
  const { invalidateActive, invalidateEvent, invalidateClosed } = useQueueInvalidation();

  const activeEventsRef = useRef(activeEvents);
  activeEventsRef.current = activeEvents;
  const activeStreamsRef = useRef(activeStreams);
  activeStreamsRef.current = activeStreams;
  const recentlyClosedRef = useRef<Set<string>>(new Set());
  const staleCandidatesRef = useRef<Set<string>>(new Set());

  useWSReconnect(() => { recentlyClosedRef.current = new Set(); });

  useEffect(() => {
    const gc = setInterval(() => {
      if (!activeEventsRef.current) return;
      const activeIds = new Set(
        activeEventsRef.current.map(e => e.id),
      );
      const { toDelete, nextCandidates } = computeGCDeletes(
        activeStreamsRef.current, activeIds, staleCandidatesRef.current,
      );
      staleCandidatesRef.current = nextCandidates;
      if (toDelete.length > 0) {
        setActiveStreams(prev => {
          const next = { ...prev };
          for (const k of toDelete) delete next[k];
          return next;
        });
      }
    }, 60_000);
    return () => clearInterval(gc);
  }, []);

  useWSMessage((msg) => {
    if (msg.type === 'progress' && msg.actor && msg.event_id) {
      const actor = msg.actor as string;
      const evtId = msg.event_id as string;
      if (recentlyClosedRef.current.has(evtId)) return;
      setActiveStreams(prev => applyProgress(prev, actor, evtId, msg.message as string));
    } else if (msg.type === 'turn') {
      const turn = msg.turn as Record<string, unknown>;
      const actor = turn?.actor as string;
      const evtId = (msg.event_id ?? '') as string;
      if (actor && evtId) {
        setActiveStreams(prev => applyTurn(prev, actor, evtId));
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'event_closed') {
      const closedId = msg.event_id as string;
      if (closedId) {
        setActiveStreams(prev => removeStreamsForEvent(prev, closedId));
        recentlyClosedRef.current.add(closedId);
        if (recentlyClosedRef.current.size > 50) {
          const oldest = recentlyClosedRef.current.values().next().value as string | undefined;
          if (oldest !== undefined) recentlyClosedRef.current.delete(oldest);
        }
        invalidateActive();
        invalidateClosed();
      }
    }
  });

  const value = useMemo<ActiveStreamsState>(() => ({ activeStreams }), [activeStreams]);

  return (
    <ActiveStreamsContext.Provider value={value}>
      {children}
    </ActiveStreamsContext.Provider>
  );
}
