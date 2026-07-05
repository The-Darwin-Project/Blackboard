// BlackBoard/ui/src/contexts/OpsStateContext.tsx
// @ai-rules:
// 1. [Pattern]: OpsControl context — user-interaction frequency state only.
// 2. [Pattern]: selectedEventId with full sessionStorage lifecycle (hydrate/set/clear).
// 3. [Pattern]: Agent registry 10s poll with cleanup. ephemeralAgents derived via useMemo.
// 4. [Pattern]: WS: event_created (auto-select), event_closed (deselect + optimistic), event_status_changed, subscription_changed, kargo_*.
// 5. [Pattern]: useWSReconnect invalidates all queries + kargo + headhunter.
// 6. [Constraint]: Must be wrapped by WebSocketProvider (uses useWSMessage, useWSConnection, useWSReconnect).
// 7. [Pattern]: Inline ref assignment for selectedEventIdRef (render phase sync for WS handlers).
import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';
import { useWSMessage, useWSConnection, useWSReconnect } from './WebSocketContext';
import { useQueueInvalidation, useActiveEvents } from '../hooks/useQueue';
import { useKargoStages, useKargoStagesInvalidation } from '../hooks/useKargo';
import { getAgents } from '../api/client';
import type { AgentRegistryEntry, KargoStageStatus } from '../api/types';

export const AGENTS = ['architect', 'sysadmin', 'developer', 'qe'] as const;

export interface ContentTile {
  id: string;
  title: string;
  content: string;
}

export interface KargoEventResult {
  status: 'created' | 'skipped' | 'error';
  detail: string;
}

export interface OpsControl {
  selectedEventId: string | null;
  selectEvent: (id: string) => void;
  deselectEvent: () => void;
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

const OpsControlContext = createContext<OpsControl | null>(null);

export function useOpsControl(): OpsControl {
  const ctx = useContext(OpsControlContext);
  if (!ctx) throw new Error('useOpsControl must be used within OpsControlProvider');
  return ctx;
}

export function OpsControlProvider({ children }: { children: ReactNode }) {
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

  selectedEventIdRef.current = selectedEventId;

  useWSReconnect(() => { invalidateAll(); invalidateKargoStages(); invalidateHeadhunter(); });

  useWSMessage((msg) => {
    if (msg.type === 'event_created' && msg.event_id) {
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

  const value = useMemo<OpsControl>(() => ({
    selectedEventId,
    selectEvent,
    deselectEvent,
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
    ephemeralAgents, registeredAgents,
    kargoStages, kargoEventResult,
    contentTiles, hotspotTileId, setHotspot, openContentTile, closeContentTile,
    autoHotspot, toggleAutoHotspot, connected, send,
  ]);

  return (
    <OpsControlContext.Provider value={value}>
      {children}
    </OpsControlContext.Provider>
  );
}
