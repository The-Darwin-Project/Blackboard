// BlackBoard/ui/src/contexts/OpsStateContext.tsx
// @ai-rules:
// 1. [Pattern]: Replaces Dashboard.tsx as the single owner of shared operational state.
// 2. [Pattern]: WS ownership: owns progress, turn, event_created, event_closed. ConversationFeed keeps brain_thinking, attachment, message_status.
// 3. [Constraint]: Must be wrapped by WebSocketProvider (uses useWSMessage, useWSConnection).
// 4. [Pattern]: Agent registry polling (10s) and ephemeral stream (keyed by event_id) sessionStorage sync live here.
// 5. [Gotcha]: Context value uses stable references (useCallback) to minimize re-renders of consumers.
import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react';
import { useWSMessage, useWSConnection, useWSReconnect } from './WebSocketContext';
import { useQueueInvalidation, useActiveEvents } from '../hooks/useQueue';
import { useKargoStages, useKargoStagesInvalidation } from '../hooks/useKargo';
import { getAgents } from '../api/client';
import type { AgentRegistryEntry, KargoStageStatus } from '../api/types';

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
    sessionStorage.setItem('darwin:selectedEventId', id);
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

  const [ephemeralStream, setEphemeralStream] = useState<Record<string, string[]>>(() => {
    try {
      const stored = sessionStorage.getItem('darwin:ephemeralStream');
      return stored ? JSON.parse(stored) : {};
    } catch { return {}; }
  });

  useEffect(() => {
    try { sessionStorage.setItem('darwin:ephemeralStream', JSON.stringify(ephemeralStream)); } catch { /* noop */ }
  }, [ephemeralStream]);

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
            ? ephemeral.filter(a => !a.bound_event_id || activeIds.includes(a.bound_event_id))
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
  const { invalidateActive, invalidateEvent, invalidateAll, invalidateClosed, invalidateHeadhunter, optimisticRemoveEvent } = useQueueInvalidation();
  const { data: activeEvents } = useActiveEvents();

  const ephemeralAgentsRef = useRef(ephemeralAgents);
  ephemeralAgentsRef.current = ephemeralAgents;
  const activeEventsRef = useRef(activeEvents);
  activeEventsRef.current = activeEvents;
  const selectedEventIdRef = useRef(selectedEventId);
  selectedEventIdRef.current = selectedEventId;

  useWSReconnect(() => { invalidateAll(); invalidateKargoStages(); invalidateHeadhunter(); });

  useWSMessage((msg) => {
    if (msg.type === 'progress' && msg.actor) {
      const actor = msg.actor as string;
      const evtId = msg.event_id as string;
      const isEphemeralEvent = evtId && (
        msg.event_source === 'headhunter'
        || msg.event_source === 'timekeeper'
        || (msg as Record<string, unknown>).subject_type === 'kargo_stage'
        || ephemeralAgentsRef.current.some((a) => a.bound_event_id === evtId)
        || activeEventsRef.current?.some((e) => e.id === evtId && (
          e.source === 'headhunter' || e.source === 'timekeeper' || e.subject_type === 'kargo_stage'
        ))
      );
      if (!isEphemeralEvent && AGENTS.includes(actor as typeof AGENTS[number])) {
        setAgentStreams((prev) => {
          const current = prev[actor] || { messages: [], eventId: null, isActive: false };
          const messages = [...current.messages, msg.message as string].slice(-MAX_BUFFER);
          return { ...prev, [actor]: { ...current, messages, eventId: evtId || current.eventId, isActive: true } };
        });
      }
      if (isEphemeralEvent && evtId) {
        setEphemeralStream((prev) => ({
          ...prev,
          [evtId]: [...(prev[evtId] || []), msg.message as string].slice(-MAX_BUFFER),
        }));
      }
    } else if (msg.type === 'turn') {
      const turn = msg.turn as Record<string, unknown>;
      const actor = turn?.actor as string;
      if (actor && AGENTS.includes(actor as typeof AGENTS[number])) {
        setAgentStreams((prev) => ({
          ...prev,
          [actor]: { ...prev[actor], isActive: false },
        }));
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'event_created' && msg.event_id) {
      selectEvent(msg.event_id as string);
      invalidateActive();
    } else if (msg.type === 'event_closed') {
      if (msg.event_id) {
        optimisticRemoveEvent(msg.event_id as string);
        invalidateEvent(msg.event_id as string);
        invalidateActive();
        invalidateClosed();
        invalidateHeadhunter();
      }
    } else if (msg.type === 'event_status_changed') {
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
