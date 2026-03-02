// BlackBoard/ui/src/components/Dashboard.tsx
// @ai-rules:
// 1. [Pattern]: 3-zone layout: Left (tabs: Activity|Chat), Middle (tabs: Tickets|Architecture), Right (collapsible MetricChart).
// 2. [Pattern]: Event selection state machine -- onEventSelect/onEventClose manage tab switching + collapse.
// 3. [Pattern]: WS ownership: Dashboard owns progress, turn, event_created, event_closed. ConversationFeed owns brain_thinking, attachment, message_status.
// 4. [Pattern]: All layout state persisted in sessionStorage with darwin: prefix for refresh resilience.
// 5. [Gotcha]: darwin:selectEvent custom event listener (from WaitingBell) lives here, NOT in ConversationFeed.
/**
 * Main dashboard with 3-zone tabbed layout.
 * Row 1: Agent streaming cards (resizable height)
 * Row 2: Left panel (Activity/Chat) | Middle panel (Tickets/Architecture) | Right panel (Resources, collapsible)
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import CytoscapeGraph from './CytoscapeGraph';
import GraphContextMenu from './GraphContextMenu';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import AgentRegistryPanel from './AgentRegistryPanel';
import HeadhunterQueuePanel from './HeadhunterQueuePanel';
import ConversationFeed from './ConversationFeed';
import AgentStreamCard from './AgentStreamCard';
import TabPanel from './TabPanel';
import ActivityStream from './ActivityStream';
import EventTicketList from './EventTicketList';
import ChatInput from './ChatInput';
import { useWSMessage, useWSConnection, useWSReconnect } from '../contexts/WebSocketContext';
import { useQueueInvalidation } from '../hooks/useQueue';
import { useEventDocument } from '../hooks/useQueue';
import type { Tab } from './TabPanel';

interface ContextMenuState {
  serviceName: string;
  position: { x: number; y: number };
}

// Resize constraints
const MIN_SIDEBAR_WIDTH = 280;
const MAX_SIDEBAR_WIDTH = 600;
const DEFAULT_SIDEBAR_WIDTH = 400;

// Storage keys -- layout uses localStorage (survives refresh + tab close),
// volatile state uses sessionStorage (clears on tab close)
const SS = {
  selectedEventId: 'darwin:selectedEventId',   // sessionStorage (volatile)
  leftTab: 'darwin:leftTab',                   // localStorage (persistent)
  middleTab: 'darwin:middleTab',               // localStorage (persistent)
  leftWidth: 'darwin:leftWidth',               // localStorage (persistent)
  agentCardHeight: 'darwin:agentCardHeight',   // localStorage (persistent)
  resourceCollapsed: 'darwin:resourceCollapsed', // localStorage (persistent)
  rightTab: 'darwin:rightTab',                   // localStorage (persistent)
} as const;

function lsGet(key: string, fallback: string): string {
  return localStorage.getItem(key) || fallback;
}

// Huddle chat message (for developer card pair programming view)
export interface HuddleMessage {
  text: string;
  actor: 'developer' | 'qe' | 'flash';
  timestamp: number;
}

// Agent stream state -- per-agent message buffers
interface AgentStreamState {
  messages: string[];
  huddleMessages: HuddleMessage[];
  eventId: string | null;
  isActive: boolean;
}

const AGENTS = ['architect', 'sysadmin', 'developer'] as const;
const MAX_BUFFER = 100;

const LEFT_TABS: Tab[] = [
  { id: 'activity', label: 'Activity' },
  { id: 'event-chat', label: 'Event Chat' },
];
const MIDDLE_TABS: Tab[] = [
  { id: 'tickets', label: 'Tickets' },
  { id: 'architecture', label: 'Architecture' },
];
const RIGHT_TABS: Tab[] = [
  { id: 'resources', label: 'Resources' },
  { id: 'agents', label: 'Agents' },
  { id: 'queue', label: 'Queue' },
];

function DashboardInner() {
  // -- Graph / inspector state (unchanged) --
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);

  // -- Layout state (localStorage-persisted -- survives refresh + tab close) --
  const [sidebarWidth, setSidebarWidth] = useState(() => parseInt(lsGet(SS.leftWidth, String(DEFAULT_SIDEBAR_WIDTH))));
  const [agentCardHeight, setAgentCardHeight] = useState(() => parseInt(lsGet(SS.agentCardHeight, '220')));
  const [resourceCollapsed, setResourceCollapsed] = useState(() => lsGet(SS.resourceCollapsed, 'false') === 'true');
  const [rightTab, setRightTab] = useState(() => lsGet(SS.rightTab, 'resources'));

  // -- Tab state (localStorage-persisted) --
  const [leftTab, setLeftTab] = useState(() => lsGet(SS.leftTab, 'activity'));
  const [middleTab, setMiddleTab] = useState(() => lsGet(SS.middleTab, 'architecture'));
  const [previousLeftTab, setPreviousLeftTab] = useState('activity');

  // -- Event selection state machine --
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    () => sessionStorage.getItem(SS.selectedEventId),
  );

  // -- Resize state --
  const [isResizing, setIsResizing] = useState(false);
  const [isResizingHeight, setIsResizingHeight] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // -- Agent streaming card state --
  const [agentStreams, setAgentStreams] = useState<Record<string, AgentStreamState>>(() => {
    const init: Record<string, AgentStreamState> = {};
    for (const a of AGENTS) init[a] = { messages: [], huddleMessages: [], eventId: null, isActive: false };
    return init;
  });

  // -- WS + query hooks --
  const { connected, send } = useWSConnection();
  const { invalidateActive, invalidateEvent, invalidateAll } = useQueueInvalidation();

  // Stale-event guard: if selected event was deleted (404), clear selection
  const { isError: selectedEventError } = useEventDocument(selectedEventId);
  useEffect(() => {
    if (selectedEventError && selectedEventId) {
      sessionStorage.removeItem(SS.selectedEventId);
      setSelectedEventId(null);
    }
  }, [selectedEventError, selectedEventId]);

  // -- Persist layout state to localStorage (survives refresh + tab close) --
  useEffect(() => { localStorage.setItem(SS.leftTab, leftTab); }, [leftTab]);
  useEffect(() => { localStorage.setItem(SS.middleTab, middleTab); }, [middleTab]);
  useEffect(() => { localStorage.setItem(SS.leftWidth, String(sidebarWidth)); }, [sidebarWidth]);
  useEffect(() => { localStorage.setItem(SS.agentCardHeight, String(agentCardHeight)); }, [agentCardHeight]);
  useEffect(() => { localStorage.setItem(SS.resourceCollapsed, String(resourceCollapsed)); }, [resourceCollapsed]);
  useEffect(() => { localStorage.setItem(SS.rightTab, rightTab); }, [rightTab]);
  // selectedEventId stays in sessionStorage (volatile -- clears on tab close, keeps on refresh)
  useEffect(() => {
    if (selectedEventId) sessionStorage.setItem(SS.selectedEventId, selectedEventId);
    else sessionStorage.removeItem(SS.selectedEventId);
  }, [selectedEventId]);

  // -- Event selection handlers --
  const onEventSelect = useCallback((id: string) => {
    setSelectedEventId(id);
    setPreviousLeftTab(leftTab);
    setLeftTab('event-chat');
    setResourceCollapsed(true);
  }, [leftTab]);

  const onEventClose = useCallback(() => {
    setSelectedEventId(null);
    setLeftTab(previousLeftTab);
    setResourceCollapsed(false);
  }, [previousLeftTab]);

  // -- darwin:selectEvent custom event listener (from WaitingBell) --
  useEffect(() => {
    const handler = (e: Event) => {
      const eventId = (e as CustomEvent).detail;
      if (eventId) onEventSelect(eventId);
    };
    window.addEventListener('darwin:selectEvent', handler);
    return () => window.removeEventListener('darwin:selectEvent', handler);
  }, [onEventSelect]);

  // -- WS reconnect: invalidate all cached queries --
  useWSReconnect(() => { invalidateAll(); });

  // -- WS message routing (Dashboard owns: progress, turn, event_created, event_closed) --
  useWSMessage((msg) => {
    if (msg.type === 'progress' && msg.actor) {
      const actor = msg.actor as string;
      if (actor === 'qe' || actor === 'flash' || actor === 'manager') {
        setAgentStreams((prev) => {
          const dev = prev['developer'] || { messages: [], huddleMessages: [], eventId: null, isActive: false };
          const displayActor = actor === 'manager' ? 'flash' : actor;
          const huddle = [...dev.huddleMessages, {
            text: msg.message as string,
            actor: displayActor as 'qe' | 'flash',
            timestamp: Date.now(),
          }].slice(-MAX_BUFFER);
          return { ...prev, developer: { ...dev, huddleMessages: huddle, isActive: true, eventId: (msg.event_id as string) || dev.eventId } };
        });
        return;
      }
      if (AGENTS.includes(actor as typeof AGENTS[number])) {
        setAgentStreams((prev) => {
          const current = prev[actor] || { messages: [], huddleMessages: [], eventId: null, isActive: false };
          const messages = [...current.messages, msg.message as string].slice(-MAX_BUFFER);
          const huddleMessages = actor === 'developer'
            ? [...current.huddleMessages, { text: msg.message as string, actor: 'developer' as const, timestamp: Date.now() }].slice(-MAX_BUFFER)
            : current.huddleMessages;
          return { ...prev, [actor]: { ...current, messages, huddleMessages, eventId: (msg.event_id as string) || current.eventId, isActive: true } };
        });
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
      onEventSelect(msg.event_id as string);
      invalidateActive();
    } else if (msg.type === 'event_closed') {
      if (msg.event_id && msg.event_id === selectedEventId) {
        onEventClose();
      }
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    }
  });

  // -- Graph handlers --
  const handleNodeClick = useCallback((serviceName: string) => {
    setSelectedService(serviceName);
  }, []);
  const handleCloseContextMenu = useCallback(() => { setContextMenu(null); }, []);

  // -- Sidebar width resize --
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left - 16;
      setSidebarWidth(Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, newWidth)));
    };
    const handleMouseUp = () => { setIsResizing(false); };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  // -- Agent card height resize --
  const startHeightResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingHeight(true);
  }, []);

  useEffect(() => {
    if (!isResizingHeight) return;
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newHeight = e.clientY - containerRect.top - 16;
      setAgentCardHeight(Math.min(400, Math.max(120, newHeight)));
    };
    const handleMouseUp = () => { setIsResizingHeight(false); };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizingHeight]);

  return (
    <div ref={containerRef} className="h-full flex flex-col p-4 overflow-hidden">
      {/* Row 1: Agent Streaming Cards - resizable height */}
      <div className="flex gap-3 flex-shrink-0" style={{ height: agentCardHeight }}>
        {AGENTS.map((agent) => (
          <AgentStreamCard
            key={agent}
            agentName={agent}
            eventId={agentStreams[agent]?.eventId || null}
            messages={agentStreams[agent]?.messages || []}
            huddleMessages={agentStreams[agent]?.huddleMessages || []}
            isActive={agentStreams[agent]?.isActive || false}
          />
        ))}
      </div>

      {/* Height resize handle */}
      <div
        className={`h-3 flex-shrink-0 flex items-center justify-center cursor-row-resize group ${
          isResizingHeight ? 'bg-accent/20' : ''
        }`}
        onMouseDown={startHeightResize}
      >
        <div className={`h-1 w-16 rounded-full transition-colors ${
          isResizingHeight ? 'bg-accent' : 'bg-border group-hover:bg-accent/60'
        }`} />
      </div>

      {/* Row 2: 3-zone content */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* LEFT PANEL: Activity | Event Chat */}
        <div
          className="flex-shrink-0 h-full bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col"
          style={{ width: sidebarWidth }}
        >
          <TabPanel tabs={LEFT_TABS} activeTab={leftTab} onTabChange={setLeftTab}>
            <div style={{ display: leftTab === 'activity' ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <ActivityStream />
            </div>
            <div style={{ display: leftTab === 'event-chat' ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              {selectedEventId ? (
                <ConversationFeed eventId={selectedEventId} onInvalidateActive={invalidateActive} onClose={onEventClose} />
              ) : (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: 13 }}>
                  Select an event from the Tickets tab to view conversation.
                </div>
              )}
            </div>
          </TabPanel>
          <ChatInput eventId={selectedEventId} wsSend={connected ? send : undefined} />
        </div>

        {/* Width resize handle */}
        <div
          className={`w-4 flex-shrink-0 flex items-center justify-center cursor-col-resize group ${
            isResizing ? 'bg-accent/20' : ''
          }`}
          onMouseDown={startResize}
        >
          <div className={`w-1 h-16 rounded-full transition-colors ${
            isResizing ? 'bg-accent' : 'bg-border group-hover:bg-accent/60'
          }`} />
        </div>

        {/* MIDDLE PANEL: Tickets | Architecture -- both mounted, inactive hidden via CSS to avoid remount */}
        <div className="flex-1 min-w-0 bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
          <TabPanel tabs={MIDDLE_TABS} activeTab={middleTab} onTabChange={setMiddleTab}>
            <div style={{ display: middleTab === 'tickets' ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <EventTicketList onEventSelect={onEventSelect} onEventClose={onEventClose} selectedEventId={selectedEventId} />
            </div>
            <div style={{ display: middleTab === 'architecture' ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden', position: 'relative' }}>
              <CytoscapeGraph
                onNodeClick={handleNodeClick}
              />
            </div>
          </TabPanel>
        </div>

        {/* RIGHT PANEL: Resource Grid (collapsible) */}
        {resourceCollapsed ? (
          /* ExpandHandle */
          <button
            onClick={() => setResourceCollapsed(false)}
            style={{
              width: 16, flexShrink: 0, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: '#1e293b', borderRadius: '0 8px 8px 0',
              borderRight: '1px solid #334155', borderTop: '1px solid #334155', borderBottom: '1px solid #334155',
              borderLeft: 'none', marginLeft: 4, padding: 0,
            }}
            title="Expand resource panel"
            aria-label="Expand resource panel"
          >
            <span style={{ color: '#64748b', fontSize: 14 }}>&#x276E;</span>
          </button>
        ) : (
          <div
            className="flex-shrink-0 ml-3 bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col"
            style={{ width: 280, transition: 'width 0.3s ease' }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <div className="flex gap-2 flex-1 min-w-0">
                {RIGHT_TABS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setRightTab(t.id)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: rightTab === t.id ? 600 : 400,
                      background: rightTab === t.id ? '#334155' : 'transparent',
                      color: rightTab === t.id ? '#e2e8f0' : '#64748b',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setResourceCollapsed(true)}
                style={{
                  background: 'transparent', border: 'none', color: '#64748b',
                  fontSize: 14, cursor: 'pointer', padding: '0 4px',
                }}
                title="Collapse"
              >
                &#x276F;
              </button>
            </div>
            <div className="flex-1 p-4 overflow-auto min-h-0">
              {rightTab === 'resources' && <MetricChart />}
              {rightTab === 'agents' && <AgentRegistryPanel />}
              {rightTab === 'queue' && <HeadhunterQueuePanel />}
            </div>
          </div>
        )}
      </div>

      {/* Node Inspector Drawer */}
      <NodeInspector
        serviceName={selectedService}
        onClose={() => { setSelectedService(null); }}
      />

      {/* Context Menu */}
      {contextMenu && (
        <GraphContextMenu
          serviceName={contextMenu.serviceName}
          position={contextMenu.position}
          onClose={handleCloseContextMenu}
        />
      )}
    </div>
  );
}

export default DashboardInner;
