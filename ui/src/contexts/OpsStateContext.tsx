// BlackBoard/ui/src/contexts/OpsStateContext.tsx
// @ai-rules:
// 1. [Pattern]: Single owner of shared operational state. WS: progress, turn, event_created, event_closed.
// 2. [Pattern]: Unified activeStreams model — no persistent/ephemeral split. Every work stream keyed
//    by `${actor}:${eventId}`. Eliminates the routing bug class (ephemeral flag races, oncall sub-check
//    timing, registry polling lag, stream leaking between tiles).
// 3. [Pattern]: Progress with actor + event_id → upsert into activeStreams. Turn → mark inactive.
//    event_closed → delete all streams for that event. No resolveStreamTarget routing needed.
// 4. [Pattern]: event_closed adds to recentlyClosedRef (FIFO cap 50). Late progress discarded.
//    Auto-deselects selectedEventId if closed event matches.
// 5. [Pattern]: Mark-and-sweep GC (60s interval, staleCandidatesRef): prune streams whose eventId
//    is no longer in active events for two consecutive cycles (120s grace).
// 6. [Constraint]: Must be wrapped by WebSocketProvider (uses useWSMessage, useWSConnection).
// 7. [Pattern]: Inline ref assignment for external-data refs (render phase sync, React 19).
//    Local-state refs sync in the callback that sets the state.
// 8. [Pattern]: ephemeralAgents derived via useMemo([registeredAgents, activeEvents]) for sidebar.
import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';
import { useWSMessage, useWSConnection, useWSReconnect } from './WebSocketContext';
import { useQueueInvalidation, useActiveEvents } from '../hooks/useQueue';
import { useKargoStages, useKargoStagesInvalidation } from '../hooks/useKargo';
import { getAgents } from '../api/client';
import type { AgentRegistryEntry, KargoStageStatus } from '../api/types';

export const AGENTS = ['architect', 'sysadmin', 'developer', 'qe'] as const;
const MAX_BUFFER = 100;

export interface ActiveStream {
  messages: string[];
  actor: string;
  eventId: string;
  isActive: boolean;
}

export interface ContentTile {
  id: string;
  title: string;
  content: string;
}

export interface KargoEventResult {
  status: 'created' | 'skipped' | 'error';
  detail: string;
}

export interface OpsState {
  selectedEventId: string | null;
  selectEvent: (id: string) => void;
  deselectEvent: () => void;
  activeStreams: Record<string, ActiveStream>;
  ephemeralAgents: AgentRegistryEntry[];
  registeredAgents: AgentRegistryEntry[];
  kargoStages: KargoStageStatus[];
  kargoEventResult: KargoEventResult | null;
  contentTiles: ContentTile[];
  hotspotTileId: string | null;
  setHotspot: (id: string | null) => void;
  openContentTile: (title: string, content: string) => void;
  closeContentTile: (id: string) => void;
  autoHotspot: boolean;
  toggleAutoHotspot: () => void;
  connected: boolean;
  send: (data: Record<string, unknown>) => void;
}

const OpsStateContext = createContext<OpsState | null>(null);

export function useOpsState(): OpsState {
  const ctx = useContext(OpsStateContext);
  if (!ctx) throw new Error('useOpsState must be used within OpsStateProvider');
  return ctx;
}

export function OpsStateProvider({ children }: { children: ReactNode }) {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    () => sessionStorage.getItem('darwin:selectedEventId'),
  );
  const selectedEventIdRef = useRef(selectedEventId);

  const selectEvent = useCallback((id: string) => {
    selectedEventIdRef.current = id;
    setSelectedEventId(id);
    try { sessionStorage.setItem('darwin:selectedEventId', id); } catch { /* quota */ }
  }, []);

  const deselectEvent = useCallback(() => {
    selectedEventIdRef.current = null;
    setSelectedEventId(null);
    sessionStorage.removeItem('darwin:selectedEventId');
  }, []);

  const [activeStreams, setActiveStreams] = useState<Record<string, ActiveStream>>({});

  const [registeredAgents, setRegisteredAgents] = useState<AgentRegistryEntry[]>([]);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const agents = await getAgents();
        setRegisteredAgents(agents);
      } catch { /* fire-and-forget */ }
    };
    fetchAgents();
    const id = setInterval(fetchAgents, 10_000);
    return () => clearInterval(id);
  }, []);

  const { data: kargoStages = [] } = useKargoStages();
  const { setKargoStages, invalidateKargoStages } = useKargoStagesInvalidation();
  const [kargoEventResult, setKargoEventResult] = useState<KargoEventResult | null>(null);

  const [contentTiles, setContentTiles] = useState<ContentTile[]>([]);
  const [hotspotTileId, setHotspot] = useState<string | null>(null);
  const [autoHotspot, setAutoHotspot] = useState(
    () => localStorage.getItem('darwin:autoHotspot') === 'true',
  );

  const toggleAutoHotspot = useCallback(() => {
    setAutoHotspot(prev => {
      const next = !prev;
      localStorage.setItem('darwin:autoHotspot', String(next));
      return next;
    });
  }, []);

  const openContentTile = useCallback((title: string, content: string) => {
    setContentTiles(prev => {
      const existing = prev.find(t => t.title === title);
      if (existing) {
        setHotspot(existing.id);
        return prev;
      }
      const id = `content-${Date.now()}`;
      setHotspot(id);
      return [...prev, { id, title, content }];
    });
  }, []);

  const closeContentTile = useCallback((id: string) => {
    setContentTiles(prev => prev.filter(t => t.id !== id));
  }, []);

  const { connected, send } = useWSConnection();
  const { invalidateActive, invalidateEvent, invalidateAll, invalidateClosed, invalidateHeadhunter, optimisticRemoveEvent, optimisticPatchEvent } = useQueueInvalidation();
  const { data: activeEvents } = useActiveEvents();

  const ephemeralAgents = useMemo(() => {
    const ephemeral = registeredAgents.filter((a: AgentRegistryEntry) => a.ephemeral);
    const activeIds = activeEvents?.map(e => e.id);
    if (!activeIds) return ephemeral;
    return ephemeral.filter(a =>
      !a.bound_event_id
      || activeIds.includes(a.bound_event_id)
      || a.bound_event_id.startsWith('nw-sweep-')
    );
  }, [registeredAgents, activeEvents]);

  const activeEventsRef = useRef(activeEvents);
  activeEventsRef.current = activeEvents;
  selectedEventIdRef.current = selectedEventId;
  const recentlyClosedRef = useRef<Set<string>>(new Set());
  const staleCandidatesRef = useRef<Set<string>>(new Set());
  const activeStreamsRef = useRef(activeStreams);
  activeStreamsRef.current = activeStreams;

  useWSReconnect(() => { invalidateAll(); invalidateKargoStages(); invalidateHeadhunter(); });

  // GC: prune streams whose event is no longer active (mark-and-sweep, 120s grace)
  useEffect(() => {
    const gc = setInterval(() => {
      const activeIds = new Set(
        (activeEventsRef.current ?? []).map(e => e.id)
      );

      const currentKeys = Object.keys(activeStreamsRef.current);
      const nowStale = currentKeys.filter(k => {
        const stream = activeStreamsRef.current[k];
        return stream && !activeIds.has(stream.eventId);
      });

      const toDelete = nowStale.filter(k => staleCandidatesRef.current.has(k));
      staleCandidatesRef.current = new Set(nowStale);

      if (toDelete.length > 0) {
        setActiveStreams((prev) => {
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
      const key = `${actor}:${evtId}`;
      setActiveStreams((prev) => {
        const current = prev[key];
        const messages = [...(current?.messages || []), msg.message as string].slice(-MAX_BUFFER);
        return { ...prev, [key]: { messages, actor, eventId: evtId, isActive: true } };
      });
    } else if (msg.type === 'turn') {
      const turn = msg.turn as Record<string, unknown>;
      const actor = turn?.actor as string;
      const evtId = (msg.event_id ?? '') as string;
      if (actor && evtId) {
        const key = `${actor}:${evtId}`;
        setActiveStreams((prev) => {
          if (!prev[key]) return { ...prev, [key]: { messages: [], actor, eventId: evtId, isActive: false } };
          return { ...prev, [key]: { ...prev[key], isActive: false } };
        });
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'event_created' && msg.event_id) {
      if (!selectedEventIdRef.current) {
        selectEvent(msg.event_id as string);
      }
      invalidateActive();
    } else if (msg.type === 'event_closed') {
      const closedId = msg.event_id as string;
      if (closedId) {
        optimisticRemoveEvent(closedId);
        invalidateEvent(closedId);
        invalidateActive();
        invalidateClosed();
        invalidateHeadhunter();

        setActiveStreams((prev) => {
          const next = { ...prev };
          let changed = false;
          for (const k of Object.keys(next)) {
            if (next[k].eventId === closedId) {
              delete next[k];
              changed = true;
            }
          }
          return changed ? next : prev;
        });

        recentlyClosedRef.current.add(closedId);
        if (recentlyClosedRef.current.size > 50) {
          const oldest = recentlyClosedRef.current.values().next().value as string | undefined;
          if (oldest !== undefined) recentlyClosedRef.current.delete(oldest);
        }

        if (closedId === selectedEventIdRef.current) {
          selectedEventIdRef.current = null;
          setSelectedEventId(null);
          sessionStorage.removeItem('darwin:selectedEventId');
        }
      }
    } else if (msg.type === 'event_status_changed') {
      if (msg.event_id && msg.status === 'deferred' && msg.defer_until) {
        optimisticPatchEvent(msg.event_id as string, {
          status: 'deferred',
          defer_until: msg.defer_until as number,
          defer_started_at: (msg.defer_started_at as number) ?? undefined,
        });
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'subscription_changed') {
      invalidateActive();
    } else if (msg.type === 'kargo_stages_update') {
      setKargoStages((msg.stages as KargoStageStatus[]) ?? []);
    } else if (msg.type === 'kargo_event_result') {
      setKargoEventResult({ status: msg.status as KargoEventResult['status'], detail: msg.detail as string });
    }
  });

  const value = useMemo<OpsState>(() => ({
    selectedEventId,
    selectEvent,
    deselectEvent,
    activeStreams,
    ephemeralAgents,
    registeredAgents,
    kargoStages,
    kargoEventResult,
    contentTiles,
    hotspotTileId,
    setHotspot,
    openContentTile,
    closeContentTile,
    autoHotspot,
    toggleAutoHotspot,
    connected,
    send,
  }), [
    selectedEventId, selectEvent, deselectEvent,
    activeStreams, ephemeralAgents, registeredAgents,
    kargoStages, kargoEventResult,
    contentTiles, hotspotTileId, setHotspot, openContentTile, closeContentTile,
    autoHotspot, toggleAutoHotspot, connected, send,
  ]);

  return (
    <OpsStateContext.Provider value={value}>
      {children}
    </OpsStateContext.Provider>
  );
}
