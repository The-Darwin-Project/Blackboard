// BlackBoard/ui/src/contexts/OpsStateContext.tsx
// @ai-rules:
// 1. [Pattern]: Single owner of shared operational state. WS: progress, turn, event_created, event_closed.
// 2. [Pattern]: resolveStreamTarget() is a named export pure function (tested in resolveStreamTarget.test.ts).
//    Backend `ephemeral` flag on progress messages is authoritative (no polling delay).
//    Fallback: agent-first routing with oncall sub-check via (bound_event_id || current_event_id) AND (current_role || role).
// 3. [Pattern]: Turn handler uses resolveStreamTarget — only mutates agentStreams when target is 'agent'.
//    Prevents oncall turn from deactivating the permanent agent tile.
// 4. [Pattern]: event_closed deletes ephemeralStream entry + adds to recentlyClosedRef (FIFO cap 50).
//    Late progress after close is discarded via recentlyClosedRef guard.
// 5. [Pattern]: Mark-and-sweep GC (60s interval, staleCandidatesRef): prune on second consecutive miss
//    (120s grace). Stale computation + ref mutation outside setState (React Strict Mode safe).
// 6. [Constraint]: agentStreams NOT cleared on close or reconnect — memory-bounded, preserves review context.
// 7. [Gotcha]: Auto-hotspot: only internal agents with isActive in agentStreams auto-promote.
// 8. [Constraint]: Must be wrapped by WebSocketProvider (uses useWSMessage, useWSConnection).
import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';
import { useWSMessage, useWSConnection, useWSReconnect } from './WebSocketContext';
import { useQueueInvalidation, useActiveEvents } from '../hooks/useQueue';
import { useKargoStages, useKargoStagesInvalidation } from '../hooks/useKargo';
import { getAgents } from '../api/client';
import type { ActiveEvent, AgentRegistryEntry, KargoStageStatus } from '../api/types';

export const AGENTS = ['architect', 'sysadmin', 'developer', 'qe'] as const;
const MAX_BUFFER = 100;

export interface AgentStreamState {
  messages: string[];
  eventId: string | null;
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
  agents: readonly string[];
  agentStreams: Record<string, AgentStreamState>;
  ephemeralStream: Record<string, string[]>;
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

export type StreamTarget = 'agent' | 'ephemeral' | 'drop';

export function resolveStreamTarget(
  actor: string,
  evtId: string,
  eventSource: string,
  subjectType: string = '',
  ephemeralAgents: AgentRegistryEntry[] = [],
  activeEvents: ActiveEvent[] | undefined = undefined,
  ephemeralFlag: boolean = false,
): StreamTarget {
  const isInternalAgent = AGENTS.includes(actor as typeof AGENTS[number]);

  // Backend ephemeral flag is authoritative and instant (no polling delay).
  // When present, it short-circuits all heuristic checks.
  if (ephemeralFlag && evtId) return 'ephemeral';

  const isEphemeralEvent = !!evtId && (
    eventSource === 'headhunter'
    || eventSource === 'timekeeper'
    || eventSource === 'nightwatcher'
    || evtId.startsWith('nw-sweep-')
    || subjectType === 'kargo_stage'
    || ephemeralAgents.some((a) => a.bound_event_id === evtId)
    || activeEvents?.some((e) => e.id === evtId && (
      e.source === 'headhunter' || e.source === 'timekeeper' || e.subject_type === 'kargo_stage'
    ))
  );

  // Oncall sub-check: ephemeral agent working on this event with matching role.
  const isBoundOncall = isInternalAgent && !!evtId &&
    ephemeralAgents.some(a =>
      (a.bound_event_id === evtId || a.current_event_id === evtId)
      && (a.current_role || a.role) === actor
    );

  if (isBoundOncall) return 'ephemeral';
  if (isInternalAgent) return 'agent';
  if (isEphemeralEvent && evtId) return 'ephemeral';
  return 'drop';
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

  const selectEvent = useCallback((id: string) => {
    setSelectedEventId(id);
    try { sessionStorage.setItem('darwin:selectedEventId', id); } catch { /* quota */ }
  }, []);

  const deselectEvent = useCallback(() => {
    setSelectedEventId(null);
    sessionStorage.removeItem('darwin:selectedEventId');
  }, []);

  const [agentStreams, setAgentStreams] = useState<Record<string, AgentStreamState>>(() => {
    const init: Record<string, AgentStreamState> = {};
    for (const a of AGENTS) init[a] = { messages: [], eventId: null, isActive: false };
    return init;
  });

  const [ephemeralStream, setEphemeralStream] = useState<Record<string, string[]>>({});

  const [ephemeralAgents, setEphemeralAgents] = useState<AgentRegistryEntry[]>([]);
  const [registeredAgents, setRegisteredAgents] = useState<AgentRegistryEntry[]>([]);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const agents = await getAgents();
        setRegisteredAgents(agents);
        const ephemeral = agents.filter((a: AgentRegistryEntry) => a.ephemeral);
        const activeIds = activeEventsRef.current?.map(e => e.id);
        setEphemeralAgents(
          activeIds && activeIds.length > 0
            ? ephemeral.filter(a =>
                !a.bound_event_id
                || activeIds.includes(a.bound_event_id)
                || a.bound_event_id.startsWith('nw-sweep-')
              )
            : ephemeral
        );
        setAgentStreams(prev => {
          const next = { ...prev };
          for (const a of AGENTS) {
            const reg = agents.find((r: AgentRegistryEntry) => r.role === a && !r.ephemeral);
            if (reg && !reg.busy && next[a]?.isActive) {
              next[a] = { ...next[a], isActive: false };
            }
          }
          return next;
        });
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

  const ephemeralAgentsRef = useRef(ephemeralAgents);
  ephemeralAgentsRef.current = ephemeralAgents;
  const activeEventsRef = useRef(activeEvents);
  activeEventsRef.current = activeEvents;
  const selectedEventIdRef = useRef(selectedEventId);
  selectedEventIdRef.current = selectedEventId;
  const recentlyClosedRef = useRef<Set<string>>(new Set());
  const staleCandidatesRef = useRef<Set<string>>(new Set());
  const ephemeralStreamRef = useRef(ephemeralStream);
  ephemeralStreamRef.current = ephemeralStream;

  useWSReconnect(() => { invalidateAll(); invalidateKargoStages(); invalidateHeadhunter(); });

  useEffect(() => {
    const gc = setInterval(() => {
      const activeIds = new Set(
        (activeEventsRef.current ?? []).map(e => e.id)
      );
      const boundIds = new Set(
        ephemeralAgentsRef.current
          .map(a => a.bound_event_id)
          .filter((id): id is string => !!id)
      );

      const currentKeys = Object.keys(ephemeralStreamRef.current);
      const nowStale = currentKeys.filter(
        k => !activeIds.has(k) && !boundIds.has(k) && !k.startsWith('nw-sweep-')
      );

      const toDelete = nowStale.filter(k => staleCandidatesRef.current.has(k));
      staleCandidatesRef.current = new Set(nowStale);

      if (toDelete.length > 0) {
        setEphemeralStream((prev) => {
          const next = { ...prev };
          for (const k of toDelete) delete next[k];
          return next;
        });
      }
    }, 60_000);
    return () => clearInterval(gc);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- refs and setter are stable

  useWSMessage((msg) => {
    if (msg.type === 'progress' && msg.actor) {
      const actor = msg.actor as string;
      const evtId = msg.event_id as string;
      if (evtId && recentlyClosedRef.current.has(evtId)) return;
      const target = resolveStreamTarget(
        actor, evtId,
        (msg.event_source ?? '') as string,
        ((msg as Record<string, unknown>).subject_type ?? '') as string,
        ephemeralAgentsRef.current,
        activeEventsRef.current,
        !!(msg as Record<string, unknown>).ephemeral,
      );
      if (target === 'agent') {
        setAgentStreams((prev) => {
          const current = prev[actor] || { messages: [], eventId: null, isActive: false };
          const messages = [...current.messages, msg.message as string].slice(-MAX_BUFFER);
          return { ...prev, [actor]: { ...current, messages, eventId: evtId || current.eventId, isActive: true } };
        });
      } else if (target === 'ephemeral') {
        setEphemeralStream((prev) => ({
          ...prev,
          [evtId]: [...(prev[evtId] || []), msg.message as string].slice(-MAX_BUFFER),
        }));
      } else {
        console.warn('[OPS] Dropped progress:', actor, evtId, msg.event_source);
      }
    } else if (msg.type === 'turn') {
      const turn = msg.turn as Record<string, unknown>;
      const actor = turn?.actor as string;
      if (actor) {
        const turnTarget = resolveStreamTarget(
          actor, (msg.event_id ?? '') as string,
          '', '',
          ephemeralAgentsRef.current,
          activeEventsRef.current,
        );
        if (turnTarget === 'agent') {
          setAgentStreams((prev) => ({
            ...prev,
            [actor]: { ...prev[actor], isActive: false },
          }));
        }
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'event_created' && msg.event_id) {
      selectEvent(msg.event_id as string);
      invalidateActive();
    } else if (msg.type === 'event_closed') {
      const closedId = msg.event_id as string;
      if (closedId) {
        optimisticRemoveEvent(closedId);
        invalidateEvent(closedId);
        invalidateActive();
        invalidateClosed();
        invalidateHeadhunter();

        setAgentStreams((prev) => {
          const next = { ...prev };
          let changed = false;
          for (const a of AGENTS) {
            if (next[a]?.eventId === closedId) {
              next[a] = { messages: [], eventId: null, isActive: false };
              changed = true;
            }
          }
          return changed ? next : prev;
        });

        setEphemeralStream((prev) => {
          if (!prev[closedId]) return prev;
          const next = { ...prev };
          delete next[closedId];
          return next;
        });

        recentlyClosedRef.current.add(closedId);
        if (recentlyClosedRef.current.size > 50) {
          const oldest = recentlyClosedRef.current.values().next().value as string | undefined;
          if (oldest !== undefined) recentlyClosedRef.current.delete(oldest);
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
    agents: AGENTS,
    agentStreams,
    ephemeralStream,
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
    agentStreams, ephemeralStream, ephemeralAgents, registeredAgents,
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
