// BlackBoard/ui/src/components/ops/EventSidebar.tsx
// @ai-rules:
// 1. [Pattern]: Persistent sidebar. Unified system state tree: Agents, Events, HH Queue, Schedules.
// 2. [Pattern]: Accordion sections (Chat, Plan, Details) appear when an event is selected. ChatInput pinned bottom.
// 3. [Pattern]: Right-click context menus per node type. Icons + color from ACTOR_COLORS and lucide-react.
// 4. [Pattern]: Resize handle on right edge. Width persisted in localStorage.
// 5. [Constraint]: ConversationFeed gets onOpenContentTile from OpsStateContext for grid content tiles.
import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Bot, Radio, GitMerge, Clock, CheckCircle2, Compass, Terminal, Code2, FlaskConical } from 'lucide-react';
import { useOpsState, AGENTS } from '../../contexts/OpsStateContext';
import { useActiveEvents, useEventDocument, useQueueInvalidation } from '../../hooks/useQueue';
import { getClosedEvents, getHeadhunterPending, type HeadhunterTodo } from '../../api/client';
import { ACTOR_COLORS, STATUS_COLORS } from '../../constants/colors';
import { useSchedules } from '../../hooks/useTimeKeeper';
import SourceIcon from '../SourceIcon';
import { TreeGroup, TreeNode, EventNode, EmptyLabel, AgentDot, EventDot } from './TreePrimitives';
import { agentMenuItems, eventMenuItems, hhMenuItems } from './sidebarMenus';
import { MOCK_EVENTS, MOCK_EVENT_DOC, MOCK_HH_TODOS, MOCK_CLOSED_EVENTS } from './mockData';
import MockConversationFeed from './MockConversationFeed';

const DEV_MODE = import.meta.env.DEV;
import { ConversationFeed } from '../ConversationFeed';
import { PlanProgress, usePlanState } from '../PlanProgress';
import ChatInput from '../ChatInput';
import CollapsibleSection from '../CollapsibleSection';
import ContextMenu, { type ContextMenuItem } from './ContextMenu';

const MIN_WIDTH = 64;
const DEFAULT_WIDTH = 500;
const MAX_WIDTH = 800;

export default function EventSidebar() {
  const { selectedEventId, selectEvent, deselectEvent, setHotspot, connected, send, openContentTile, registeredAgents } = useOpsState();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const handler = () => setCollapsed(c => !c);
    window.addEventListener('darwin:toggleSidebar', handler);
    return () => window.removeEventListener('darwin:toggleSidebar', handler);
  }, []);

  const [width, setWidth] = useState(() => {
    const stored = localStorage.getItem('darwin:sidebarWidth');
    return stored ? parseInt(stored) : DEFAULT_WIDTH;
  });
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; items: ContextMenuItem[] } | null>(null);

  useEffect(() => {
    if (!collapsed) localStorage.setItem('darwin:sidebarWidth', String(width));
  }, [width, collapsed]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      if (!sidebarRef.current) return;
      const rect = sidebarRef.current.getBoundingClientRect();
      setWidth(Math.min(MAX_WIDTH, Math.max(DEFAULT_WIDTH, e.clientX - rect.left)));
    };
    const onUp = () => setIsResizing(false);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  // Data sources
  const { data: activeEvents } = useActiveEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(20),
    refetchInterval: 10_000,
  });
  const [hhTodos, setHhTodos] = useState<HeadhunterTodo[]>([]);
  const [hhError, setHhError] = useState(false);
  const { data: schedules = [] } = useSchedules();
  const { invalidateActive } = useQueueInvalidation();

  useEffect(() => {
    const fetchHH = async () => {
      try { setHhTodos(await getHeadhunterPending()); setHhError(false); }
      catch { setHhError(true); }
    };
    fetchHH();
    const id = setInterval(fetchHH, 30_000);
    return () => clearInterval(id);
  }, []);

  const { data: eventDoc, isLoading: docLoading, isError: docError } = useEventDocument(selectedEventId);
  const { hasPlan } = usePlanState(eventDoc?.conversation || []);

  if (collapsed) {
    return (
      <div className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex flex-col items-center py-3 gap-3"
        style={{ width: MIN_WIDTH }}>
        <button onClick={() => setCollapsed(false)}
          className="p-1.5 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-secondary transition-colors"
          title="Expand sidebar">
          <ChevronRight size={21} />
        </button>
        <div className="w-6 h-px bg-border" />
        <div className="flex flex-col items-center gap-2">
          <AgentDot count={registeredAgents.length} active={registeredAgents.filter(a => a.busy).length} />
          <EventDot count={activeEvents?.length || 0} />
        </div>
      </div>
    );
  }

  const isDemoMode = DEV_MODE && (!activeEvents || activeEvents.length === 0);
  const events = isDemoMode ? MOCK_EVENTS : activeEvents || [];
  const demoHH = isDemoMode ? MOCK_HH_TODOS : hhTodos;
  const closedSource = isDemoMode ? MOCK_CLOSED_EVENTS : (closedEvents || []);
  const recentClosed = closedSource.filter((evt: { created?: string }) => {
    if (!evt.created) return false;
    return Date.now() - new Date(evt.created).getTime() < 30 * 60 * 1000;
  });
  const activeEvts = events.filter(e => e.status === 'active' || e.status === 'new');
  const waitingEvts = events.filter(e => e.status === 'waiting_approval');
  const deferredEvts = events.filter(e => e.status === 'deferred');
  const isMockEvent = isDemoMode && selectedEventId?.startsWith('evt-demo');

  return (
    <div ref={sidebarRef} className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex relative"
      style={{ width }}>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <div className="px-3 py-2 border-b border-border flex items-center justify-between flex-shrink-0">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">System</span>
          <button onClick={() => setCollapsed(true)}
            className="p-1 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-secondary transition-colors"
            title="Collapse sidebar">
            <ChevronLeft size={18} />
          </button>
        </div>

        {/* Tree + event detail area */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {/* System tree - constrained when event selected so chat gets remaining space */}
          <div className={`overflow-auto ${selectedEventId ? 'flex-shrink-0' : 'flex-1'}`}
            style={selectedEventId ? { maxHeight: '35vh' } : undefined}>
          <CollapsibleSection title="System" defaultOpen={!selectedEventId} badge={
            <span className="text-[12px] text-text-muted">{AGENTS.length + events.length + demoHH.length + schedules.length}</span>
          }>
            <div className="px-0.5">
            {/* Agents Group */}
            <TreeGroup icon={<Bot size={16} />} label="Agents" count={registeredAgents.length}
              countColor={registeredAgents.some(a => a.busy) ? '#22c55e' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {AGENTS.map(name => {
                const reg = registeredAgents.find(r => r.role === name && !r.ephemeral);
                const isBusy = reg?.busy || false;
                const isRegistered = !!reg;
                const color = ACTOR_COLORS[name] || '#6b7280';
                const AgentIcon = ({ architect: Compass, sysadmin: Terminal, developer: Code2, qe: FlaskConical } as Record<string, typeof Compass>)[name];
                return (
                  <TreeNode key={name}
                    icon={
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{
                            background: isBusy ? '#22c55e' : isRegistered ? '#22c55e80' : '#334155',
                            boxShadow: isBusy ? '0 0 6px #22c55e80' : 'none',
                            transition: 'all 0.3s',
                          }} />
                        {AgentIcon && <AgentIcon size={14} style={{ color }} />}
                      </span>
                    }
                    label={name}
                    labelColor={color}
                    sublabel={isBusy ? reg?.current_event_id?.slice(0, 12) : isRegistered ? 'idle' : 'offline'}
                    sublabelColor={isBusy ? '#22c55e' : undefined}
                    onClick={() => setHotspot(name)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setCtxMenu({ x: e.clientX, y: e.clientY, items: agentMenuItems(name, reg, setHotspot) });
                    }}
                  />
                );
              })}
            </TreeGroup>

            {/* Events Group -- never forceCollapsed so user can hot-swap between events */}
            <TreeGroup icon={<Radio size={16} />} label="Events" count={events.length}
              countColor={events.length > 0 ? '#3b82f6' : '#64748b'}>
              {events.length === 0 && <EmptyLabel>No active events</EmptyLabel>}
              {activeEvts.map(evt => (
                <EventNode key={evt.id} evt={evt} isSelected={selectedEventId === evt.id}
                  onClick={() => selectEvent(evt.id)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: eventMenuItems(evt, selectEvent, send, connected) });
                  }}
                />
              ))}
              {waitingEvts.map(evt => (
                <EventNode key={evt.id} evt={evt} isSelected={selectedEventId === evt.id}
                  onClick={() => selectEvent(evt.id)}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: eventMenuItems(evt, selectEvent, send, connected) });
                  }}
                />
              ))}
              {deferredEvts.length > 0 && (
                <TreeGroup icon={<Clock size={13} />} label="Deferred" count={deferredEvts.length} nested>
                  {deferredEvts.map(evt => (
                    <EventNode key={evt.id} evt={evt} isSelected={selectedEventId === evt.id}
                      onClick={() => selectEvent(evt.id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setCtxMenu({ x: e.clientX, y: e.clientY, items: eventMenuItems(evt, selectEvent, send, connected) });
                      }}
                    />
                  ))}
                </TreeGroup>
              )}
              {recentClosed.length > 0 && (
                <TreeGroup icon={<CheckCircle2 size={13} />} label="Recently Closed" count={recentClosed.length} nested
                  countColor="#22c55e">
                  {recentClosed.map(evt => (
                    <EventNode key={evt.id} evt={evt} isSelected={selectedEventId === evt.id}
                      onClick={() => selectEvent(evt.id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setCtxMenu({ x: e.clientX, y: e.clientY, items: eventMenuItems(evt, selectEvent, send, connected) });
                      }}
                    />
                  ))}
                </TreeGroup>
              )}
            </TreeGroup>

            {/* HH Queue Group */}
            <TreeGroup icon={<GitMerge size={16} />} label="Headhunter Queue" count={demoHH.length}
              countColor={demoHH.length > 0 ? '#f59e0b' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {hhError && <EmptyLabel>Failed to load queue</EmptyLabel>}
              {!hhError && demoHH.length === 0 && <EmptyLabel>No pending todos</EmptyLabel>}
              {demoHH.map(todo => (
                <TreeNode key={todo.todo_id}
                  icon={<SourceIcon source="headhunter" size={18} />}
                  label={`!${todo.mr_iid} ${todo.mr_title?.slice(0, 30) || ''}`}
                  sublabel={todo.action.replace(/_/g, ' ')}
                  sublabelColor={todo.pipeline_status === 'failed' ? '#ef4444' : '#64748b'}
                  onClick={() => window.open(todo.target_url, '_blank')}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: hhMenuItems(todo) });
                  }}
                />
              ))}
            </TreeGroup>

            {/* Schedules Group */}
            <TreeGroup icon={<Clock size={16} />} label="Schedules" count={schedules.length}
              countColor={schedules.length > 0 ? '#818cf8' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {schedules.length === 0 && <EmptyLabel>No schedules</EmptyLabel>}
              {schedules.map(sched => (
                <TreeNode key={sched.id}
                  icon={<SourceIcon source="timekeeper" size={18} />}
                  label={sched.name}
                  sublabel={sched.schedule_type === 'recurring' ? (sched.cron || 'recurring') : 'one-shot'}
                  sublabelColor={sched.enabled ? '#818cf8' : '#475569'}
                  style={{ opacity: sched.enabled ? 1 : 0.5 }}
                />
              ))}
            </TreeGroup>
            </div>
          </CollapsibleSection>
          </div>

          {/* Event detail area -- takes remaining vertical space */}
          {selectedEventId && (() => {
            if (isMockEvent) { /* fall through to render with MOCK_EVENT_DOC */ }
            else if (docLoading) {
              return (
                <div className="flex-1 min-h-0 flex items-center justify-center border-t border-border">
                  <div className="text-center text-text-muted text-sm animate-pulse">Loading event...</div>
                </div>
              );
            } else if (docError || !eventDoc) {
              return (
                <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-2 border-t border-border px-4">
                  <span className="text-text-muted text-sm">Event conversation unavailable</span>
                  <span className="text-text-muted text-xs">Document may have been archived or cleaned up.</span>
                  <button onClick={deselectEvent}
                    className="mt-2 text-xs px-3 py-1 rounded border border-border hover:bg-bg-tertiary text-text-secondary transition-colors">
                    Close
                  </button>
                </div>
              );
            }
            const doc = isMockEvent ? MOCK_EVENT_DOC : eventDoc!;
            const planTurns = doc.conversation.filter((t: { action: string }) => t.action === 'plan');
            const completedSteps = doc.conversation.filter((t: { action: string; evidence?: string }) => t.action === 'plan_step' && t.evidence === 'completed').length;
            const showPlan = planTurns.length > 0 || hasPlan;
            return (
              <div className="flex-1 min-h-0 flex flex-col overflow-hidden border-t border-border">
                <div className="flex-shrink-0 px-1.5 pt-2 pb-1">
                <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg border"
                  style={{ background: `${STATUS_COLORS[doc.status]?.border || '#3b82f6'}08`, borderColor: `${STATUS_COLORS[doc.status]?.border || '#3b82f6'}30` }}>
                  {isDemoMode && <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-semibold flex-shrink-0">DEMO</span>}
                  <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: STATUS_COLORS[doc.status]?.border || '#3b82f6' }} />
                  <SourceIcon source={doc.source} size={16} />
                  <span className="text-[13px] font-mono truncate flex-1" style={{ color: STATUS_COLORS[doc.status]?.text || '#93c5fd' }}>{selectedEventId}</span>
                  <span className="text-[11px] px-1.5 py-0.5 rounded font-medium flex-shrink-0"
                    style={{ background: STATUS_COLORS[doc.status]?.bg || '#1e293b', color: STATUS_COLORS[doc.status]?.text || '#93c5fd' }}>
                    {STATUS_COLORS[doc.status]?.label || doc.status}
                  </span>
                  <button onClick={deselectEvent}
                    className="flex items-center justify-center w-6 h-6 rounded border border-border hover:border-red-500/50 hover:bg-red-500/10 text-text-muted hover:text-red-400 transition-colors text-sm font-bold flex-shrink-0"
                    title="Close event">&times;</button>
                </div>
                </div>

                {/* Chat -- flex-1, takes remaining vertical space with independent scroll */}
                <CollapsibleSection title="Chat" defaultOpen flexContent badge={
                  <span className="text-[12px] text-text-muted">{doc.conversation.length}</span>
                }>
                  {isMockEvent
                    ? <MockConversationFeed />
                    : <ConversationFeed eventId={selectedEventId} onInvalidateActive={invalidateActive} onOpenContentTile={openContentTile} />
                  }
                </CollapsibleSection>

                {/* Plan + Details -- fixed at bottom with constrained height */}
                <div className="flex-shrink-0 overflow-auto px-1.5 pb-1" style={{ maxHeight: '25vh' }}>
                  {showPlan && (
                    <CollapsibleSection title="Plan" badge={
                      <span className="text-[12px] text-text-muted">{completedSteps}/4</span>
                    }>
                      <PlanProgress conversation={doc.conversation as import('../../api/types').ConversationTurn[]} />
                    </CollapsibleSection>
                  )}
                  <CollapsibleSection title="Details">
                    <div className="space-y-1.5 text-[13px] text-text-muted">
                      <div className="flex justify-between"><span>Source</span><span className="flex items-center gap-1"><SourceIcon source={doc.source} size={18} />{doc.source}</span></div>
                      <div className="flex justify-between"><span>{(doc as any).subject_type === 'kargo_stage' ? 'Stage' : 'Service'}</span><span className="text-text-secondary">{doc.service}</span></div>
                      <div className="flex justify-between"><span>Status</span>
                        <span className="px-1.5 py-0.5 rounded text-[12px] font-medium"
                          style={{ background: STATUS_COLORS[doc.status]?.bg || '#1e293b', color: STATUS_COLORS[doc.status]?.text || '#94a3b8' }}>
                          {doc.status}
                        </span>
                      </div>
                      <div className="flex justify-between"><span>Turns</span><span>{doc.conversation.length}</span></div>
                    </div>
                  </CollapsibleSection>
                </div>
              </div>
            );
          })()}
        </div>

        {/* ChatInput pinned bottom -- always visible. Creates new events when no event selected, sends messages to active event when selected. */}
        <div className="flex-shrink-0 border-t border-border">
          <ChatInput eventId={selectedEventId} wsSend={connected ? send as (msg: object) => void : undefined} />
        </div>
      </div>

      {/* Resize handle */}
      <div className={`absolute top-0 right-0 w-1.5 h-full cursor-col-resize group ${isResizing ? 'bg-accent/30' : ''}`}
        onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>

      {/* Context menu */}
      {ctxMenu && <ContextMenu x={ctxMenu.x} y={ctxMenu.y} items={ctxMenu.items} onClose={() => setCtxMenu(null)} />}
    </div>
  );
}

