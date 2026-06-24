// BlackBoard/ui/src/components/ops/EventSidebar.tsx
// @ai-rules:
// 1. [Pattern]: Persistent sidebar. Unified system state tree: Agents, Events, HH Queue, Schedules.
// 2. [Pattern]: Event detail area extracted to EventChatPanel. Sidebar is tree-only + new-event ChatInput.
// 3. [Pattern]: Right-click context menus per node type. Icons + color from ACTOR_COLORS and lucide-react.
// 4. [Pattern]: Resize handle on right edge. Width persisted in localStorage.
// 5. [Pattern]: ctxMenu cleared on all collapse paths (collapseSidebar, toggleSidebar, chevron button).
// 6. [Pattern]: ChatInput only visible when !selectedEventId (event chat lives in EventChatPanel).
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Bot, Radio, GitMerge, Clock, CheckCircle2, Compass, Terminal, Code2, FlaskConical, Snowflake, Shield } from 'lucide-react';
import { useOpsState, AGENTS } from '../../contexts/OpsStateContext';
import { useActiveEvents, useWaitingApprovalEvents, useHeadhunterPending } from '../../hooks/useQueue';
import { getClosedEvents } from '../../api/client';
import { ACTOR_COLORS } from '../../constants/colors';
import { useSchedules } from '../../hooks/useTimeKeeper';
import { useJiraMissions, useJiraActions } from '../../hooks/useJira';
import SourceIcon from '../SourceIcon';
import { TreeGroup, TreeNode, EventNode, EmptyLabel, AgentDot, EventDot } from './TreePrimitives';
import { agentMenuItems, eventMenuItems, hhMenuItems, kargoStageMenuItems, jiraMissionMenuItems } from './sidebarMenus';
import { safeOpen } from '../../utils/safeOpen';
import { MOCK_EVENTS, MOCK_HH_TODOS, MOCK_CLOSED_EVENTS } from './mockData';

const DEV_MODE = import.meta.env.DEV;
import ChatInput from '../ChatInput';
import CollapsibleSection from '../CollapsibleSection';
import ContextMenu, { type ContextMenuItem } from './ContextMenu';

const MIN_WIDTH = 64;
const DEFAULT_WIDTH = 500;
const EXPANDED_MIN_WIDTH = 250;
const MAX_WIDTH = 800;

export default function EventSidebar() {
  const { selectedEventId, selectEvent, setHotspot, connected, send, openContentTile, registeredAgents, kargoStages } = useOpsState();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const toggle = () => { setCollapsed(c => !c); setCtxMenu(null); };
    const collapse = () => { setCollapsed(true); setCtxMenu(null); };
    const expand = () => setCollapsed(false);
    window.addEventListener('darwin:toggleSidebar', toggle);
    window.addEventListener('darwin:collapseSidebar', collapse);
    window.addEventListener('darwin:expandSidebar', expand);
    return () => {
      window.removeEventListener('darwin:toggleSidebar', toggle);
      window.removeEventListener('darwin:collapseSidebar', collapse);
      window.removeEventListener('darwin:expandSidebar', expand);
    };
  }, []);

  const { size: width, isResizing, startResize, panelRef: sidebarRef } = useResizablePanel({
    direction: 'horizontal', min: EXPANDED_MIN_WIDTH, max: MAX_WIDTH, defaultSize: DEFAULT_WIDTH,
    storageKey: 'darwin:sidebarWidth', enabled: !collapsed,
  });

  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; items: ContextMenuItem[] } | null>(null);

  // Data sources
  const { data: activeEvents } = useActiveEvents();
  const { data: waitingApprovalEvents } = useWaitingApprovalEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(20),
    refetchInterval: 10_000,
  });
  const { data: hhTodos = [], isError: hhError } = useHeadhunterPending();
  const { data: jiraMissions = [] } = useJiraMissions();
  const jiraActions = useJiraActions();
  const { data: schedules = [] } = useSchedules();

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
  const recentClosed = closedSource;
  const activeEvts = events.filter(e => e.status === 'active' || e.status === 'new');
  const deferredEvts = events.filter(e => e.status === 'deferred');
  const approvalEvts = isDemoMode ? [] : (waitingApprovalEvents || []);

  return (
    <div ref={sidebarRef} className="flex-shrink-0 h-full bg-bg-secondary border-r border-border flex relative"
      style={{ width }}>
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <div className="px-3 py-2 border-b border-border flex items-center justify-between flex-shrink-0">
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">System</span>
          <button onClick={() => { setCollapsed(true); setCtxMenu(null); }}
            className="p-1 rounded hover:bg-bg-tertiary text-text-muted hover:text-text-secondary transition-colors"
            title="Collapse sidebar">
            <ChevronLeft size={18} />
          </button>
        </div>

        {/* Tree + event detail area */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {/* System tree - constrained when event selected so chat gets remaining space */}
          <div className="overflow-auto flex-1">
          <CollapsibleSection title="System" defaultOpen={!selectedEventId} badge={
            <span className="text-[12px] text-text-muted">{AGENTS.length + events.length + kargoStages.length + demoHH.length + schedules.length}</span>
          }>
            <div className="px-0.5">
            {/* Agents Group */}
            <TreeGroup icon={<Bot size={16} />} label="Agents"
              count={AGENTS.length + registeredAgents.filter(a => a.ephemeral).length}
              countColor={registeredAgents.some(a => a.busy) ? '#22c55e' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {AGENTS.map(name => {
                const reg = registeredAgents.find(r => r.role === name && !r.ephemeral);
                const isBusy = reg?.busy || false;
                const isRegistered = !!reg;
                const color = ACTOR_COLORS[name] || '#6b7280';
                const AgentIcon = ({ architect: Compass, sysadmin: Terminal, developer: Code2, qe: FlaskConical, security_analyst: Shield } as Record<string, typeof Compass>)[name];
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
              {/* OnCall (ephemeral) agents */}
              {registeredAgents.filter(a => a.ephemeral).map(a => {
                const displayRole = a.current_role || a.role || 'oncall';
                const color = ACTOR_COLORS[displayRole] || '#8b5cf6';
                return (
                  <TreeNode key={a.agent_id}
                    icon={
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{
                            background: a.busy ? '#8b5cf6' : '#8b5cf680',
                            boxShadow: a.busy ? '0 0 6px #8b5cf680' : 'none',
                            transition: 'all 0.3s',
                          }} />
                        <Bot size={14} style={{ color }} />
                      </span>
                    }
                    label={`${displayRole}`}
                    labelColor={color}
                    sublabel={a.bound_event_id?.slice(4, 16) || (a.busy ? 'working' : 'idle')}
                    sublabelColor={a.busy ? '#8b5cf6' : undefined}
                    onClick={() => {
                      if (a.bound_event_id?.startsWith('nw-sweep-')) {
                        setHotspot(a.bound_event_id);
                      } else if (a.bound_event_id) {
                        selectEvent(a.bound_event_id);
                      }
                    }}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setCtxMenu({ x: e.clientX, y: e.clientY, items: agentMenuItems(displayRole, a, setHotspot) });
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
              <TreeGroup icon={<Snowflake size={13} />} label="Waiting for Approval" count={approvalEvts.length} nested
                  countColor={approvalEvts.length > 0 ? '#f59e0b' : '#475569'} forceCollapsed={approvalEvts.length === 0}>
                  {approvalEvts.length === 0 && <EmptyLabel>No pending approvals</EmptyLabel>}
                  {approvalEvts.map(evt => (
                    <EventNode key={evt.id} evt={evt} isSelected={selectedEventId === evt.id}
                      onClick={() => selectEvent(evt.id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setCtxMenu({ x: e.clientX, y: e.clientY, items: eventMenuItems(evt, selectEvent, send, connected) });
                      }}
                    />
                  ))}
                </TreeGroup>
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
                  <Link to="/reports" className="block px-4 py-1.5 text-[11px] text-accent hover:underline">
                    View all in Event History &rarr;
                  </Link>
                </TreeGroup>
              )}
            </TreeGroup>

            {/* Jira Missions Group */}
            <TreeGroup icon={<SourceIcon source="headhunter" subjectType="jira" size={16} />} label="Jira Missions" count={jiraMissions.length}
              countColor={jiraMissions.length > 0 ? '#2684FF' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {jiraMissions.length === 0 && <EmptyLabel>No Jira missions</EmptyLabel>}
              {jiraMissions.map(m => (
                <TreeNode key={m.key}
                  icon={<SourceIcon source="headhunter" subjectType="jira" size={14} />}
                  label={m.key}
                  sublabel={m.phase}
                  sublabelColor={m.phase === 'analyzed' ? '#22c55e' : m.phase === 'approved' ? '#3b82f6' : '#64748b'}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: jiraMissionMenuItems(m, openContentTile, jiraActions) });
                  }}
                />
              ))}
            </TreeGroup>

            {/* Kargo Stages Group */}
            <TreeGroup icon={<SourceIcon source="aligner" subjectType="kargo_stage" size={16} />} label="Kargo Stages" count={kargoStages.length}
              countColor={kargoStages.length > 0 ? '#ef4444' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {kargoStages.length === 0 && <EmptyLabel>No failed stages</EmptyLabel>}
              {Object.entries(
                kargoStages.reduce<Record<string, typeof kargoStages>>((acc, s) => {
                  (acc[s.project] ??= []).push(s);
                  return acc;
                }, {}),
              ).map(([project, stages]) => (
                <TreeGroup key={project} icon={<SourceIcon source="aligner" subjectType="kargo_stage" size={13} />} label={project} count={stages.length} nested
                  countColor="#ef4444">
                  {stages.map(s => (
                    <TreeNode key={`${s.project}/${s.stage}`}
                      icon={<SourceIcon source="aligner" subjectType="kargo_stage" size={18} />}
                      label={s.stage}
                      sublabel={s.failed_step || s.phase}
                      sublabelColor="#ef4444"
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setCtxMenu({ x: e.clientX, y: e.clientY, items: kargoStageMenuItems(s, send, connected) });
                      }}
                    />
                  ))}
                </TreeGroup>
              ))}
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
                  onClick={() => safeOpen(todo.target_url)}
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

        </div>

        {/* ChatInput pinned bottom -- creates new events. Hidden when event selected (chat moves to EventChatPanel). */}
        {!collapsed && !selectedEventId && (
          <div className="flex-shrink-0 border-t border-border">
            <ChatInput wsSend={connected ? send as (msg: object) => void : undefined} />
          </div>
        )}
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

