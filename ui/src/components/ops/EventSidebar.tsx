// BlackBoard/ui/src/components/ops/EventSidebar.tsx
// @ai-rules:
// 1. [Pattern]: Persistent sidebar. Unified system state tree: Agents, Events, ArgoCD Queue, Jenkins Queue, Jira, Kargo, HH Queue, Schedules.
// 2. [Pattern]: Event detail area extracted to EventChatPanel. Sidebar is tree-only + new-event ChatInput.
// 3. [Pattern]: Right-click context menus per node type. Icons + color from ACTOR_COLORS and lucide-react.
// 4. [Pattern]: Resize handle on right edge. Width persisted in localStorage.
// 5. [Pattern]: ctxMenu cleared on all collapse paths (collapseSidebar, toggleSidebar, chevron button).
// 6. [Pattern]: ChatInput only visible when !selectedEventId (event chat lives in EventChatPanel).
// 7. [Pattern]: Agents tree is driven ONLY by registeredAgents (no static/offline ghost rows). partitionAgents() precedence:
//    bound_event_id 'nw-*' -> Sensors; other bound_event_id -> Squad (even for sensor roles); unbound + SENSOR_ROLES -> Sensors; else Standalone.
//    Sensor/role checks use the DISPLAY role (current_role || role) because on-call agents register with role '' and only get current_role per dispatch.
// 8. [Gotcha]: Agent click routing: 'nw-sweep-*' -> setHotspot(boundId); other 'nw-*' and unbound -> setHotspot(role); other bound -> selectEvent.
//    Never selectEvent a non-event id. An agent with no resolvable role (label falls back to 'oncall') is a click no-op: 'oncall' is not a tile id.
// 9. [Gotcha]: Squads are shown for every bound_event_id in the registry, even if the event is not in active/recently-closed lists (stale or beyond the 20-item closed window): label falls back to 'Squad • <shortId>'.
//    Registry is authoritative; OpsStateContext.ephemeralAgents does the active-event filtering for other consumers.
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Bot, Radio, GitMerge, Clock, CheckCircle2, Compass, Terminal, Code2, FlaskConical, Snowflake, Shield, Users, Radar } from 'lucide-react';
import type { AgentRegistryEntry } from '../../api/types';
import { useOpsControl } from '../../contexts/OpsStateContext';
import { useActiveEvents, useWaitingApprovalEvents, useHeadhunterPending, useAlignerPending, useJenkinsPending } from '../../hooks/useQueue';
import { getClosedEvents } from '../../api/client';
import { ACTOR_COLORS } from '../../constants/colors';
import { useSchedules } from '../../hooks/useTimeKeeper';
import { useJiraMissions, useJiraActions } from '../../hooks/useJira';
import SourceIcon, { JenkinsIcon } from '../SourceIcon';
import { TreeGroup, TreeNode, EventNode, EmptyLabel, AgentDot, EventDot } from './TreePrimitives';
import {
  agentMenuItems, eventMenuItems, hhMenuItems, alignerPendingMenuItems,
  jenkinsQueueMenuItems, kargoStageMenuItems, jiraMissionMenuItems,
  formatHeadhunterLabel, getHeadhunterItemKey, isGitHubTodo,
} from './sidebarMenus';
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

const ROLE_ICONS: Record<string, React.ComponentType<{ size?: number; style?: React.CSSProperties; className?: string }>> = {
  architect: Compass,
  sysadmin: Terminal,
  developer: Code2,
  qe: FlaskConical,
  security_analyst: Shield,
  code_reviewer: Code2,
  explorer: Compass,
  aligner: Radar,
  headhunter: GitMerge,
  timekeeper: Clock,
  nightwatcher: Radar,
};

const ROLE_SORT_ORDER: Record<string, number> = {
  architect: 1,
  developer: 2,
  sysadmin: 3,
  qe: 4,
  security_analyst: 5,
  code_reviewer: 6,
  explorer: 7,
  aligner: 8,
  headhunter: 9,
  timekeeper: 10,
  nightwatcher: 11,
};

const UNKNOWN_ROLE_SORT = 99;
const FALLBACK_ROLE_LABEL = 'oncall';
const FALLBACK_ROLE_COLOR = '#8b5cf6';
const BUSY_COLOR = '#22c55e';
const IDLE_COUNT_COLOR = '#64748b';

/** Roles that identify sensor / on-call sweep agents when they are not bound to an event. */
const SENSOR_ROLES = new Set(['aligner', 'headhunter', 'timekeeper', 'nightwatcher']);

/** Role shown for an agent: per-dispatch current_role wins over the registered role. May be ''. */
const resolveAgentRole = (a: AgentRegistryEntry): string => a.current_role || a.role || '';

interface AgentGroups {
  squads: Map<string, AgentRegistryEntry[]>;
  sensors: AgentRegistryEntry[];
  standalone: AgentRegistryEntry[];
}

/** Split registered agents into event squads, sensors and standalone (see @ai-rules 7). */
function partitionAgents(agents: AgentRegistryEntry[]): AgentGroups {
  const groups: AgentGroups = { squads: new Map(), sensors: [], standalone: [] };
  for (const a of agents) {
    const bound = a.bound_event_id;
    if (bound?.startsWith('nw-')) {
      groups.sensors.push(a);
    } else if (bound) {
      const list = groups.squads.get(bound) ?? [];
      list.push(a);
      groups.squads.set(bound, list);
    } else if (SENSOR_ROLES.has(resolveAgentRole(a))) {
      groups.sensors.push(a);
    } else {
      groups.standalone.push(a);
    }
  }
  return groups;
}

function sortAgents(list: AgentRegistryEntry[]): AgentRegistryEntry[] {
  return [...list].sort((a, b) => {
    const roleA = resolveAgentRole(a);
    const roleB = resolveAgentRole(b);
    const orderA = ROLE_SORT_ORDER[roleA] ?? UNKNOWN_ROLE_SORT;
    const orderB = ROLE_SORT_ORDER[roleB] ?? UNKNOWN_ROLE_SORT;
    return orderA - orderB || roleA.localeCompare(roleB);
  });
}

/** Busy: task id, else event id (both truncated), else 'working'. Idle: 'idle'. */
function agentSublabel(a: AgentRegistryEntry): string {
  if (!a.busy) return 'idle';
  const id = a.current_task_id || a.current_event_id;
  return id ? id.slice(0, 12) : 'working';
}

const groupCountColor = (list: AgentRegistryEntry[]): string =>
  list.some(a => a.busy) ? BUSY_COLOR : IDLE_COUNT_COLOR;

const shortEventId = (eventId: string): string =>
  eventId.startsWith('evt-') ? eventId.slice(4, 12) : eventId.slice(0, 8);

const squadLabelFor = (eventId: string, service?: string): string =>
  service ? `Squad • ${service} (${shortEventId(eventId)})` : `Squad • ${shortEventId(eventId)}`;

export default function EventSidebar() {
  const { selectedEventId, selectEvent, setHotspot, connected, send, openContentTile, registeredAgents, kargoStages } = useOpsControl();
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
  const { data: alignerPending = [] } = useAlignerPending();
  const { data: jenkinsPending = [] } = useJenkinsPending();
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

  const { squads: squadGroups, sensors: sensorAgents, standalone: standaloneAgents } = partitionAgents(registeredAgents);

  const renderAgentNode = (a: AgentRegistryEntry) => {
    const role = resolveAgentRole(a);
    const displayRole = role || FALLBACK_ROLE_LABEL;
    const color = ACTOR_COLORS[role] || FALLBACK_ROLE_COLOR;
    const AgentIcon = ROLE_ICONS[role] || Bot;
    const isBusy = a.busy;
    // 'oncall' is only a display label, not a grid tile id: never focus it.
    const focusTile = (id: string | null) => { if (role) setHotspot(id); };

    return (
      <TreeNode
        key={a.agent_id}
        icon={
          <span className="flex items-center gap-1.5">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{
                background: isBusy ? BUSY_COLOR : `${BUSY_COLOR}80`,
                boxShadow: isBusy ? `0 0 6px ${BUSY_COLOR}80` : 'none',
                transition: 'all 0.3s',
              }}
            />
            <AgentIcon size={14} style={{ color }} />
          </span>
        }
        label={displayRole}
        labelColor={color}
        sublabel={agentSublabel(a)}
        sublabelColor={isBusy ? BUSY_COLOR : undefined}
        onClick={() => {
          const bound = a.bound_event_id;
          if (bound?.startsWith('nw-sweep-')) {
            setHotspot(bound);
          } else if (bound && !bound.startsWith('nw-')) {
            selectEvent(bound);
          } else {
            focusTile(role);
          }
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          setCtxMenu({ x: e.clientX, y: e.clientY, items: agentMenuItems(displayRole, a, focusTile) });
        }}
      />
    );
  };

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
            <span className="text-[12px] text-text-muted">{registeredAgents.length + events.length + kargoStages.length + demoHH.length + schedules.length}</span>
          }>
            <div className="px-0.5">
            {/* Agents Group */}
            <TreeGroup icon={<Bot size={16} />} label="Agents"
              count={registeredAgents.length}
              countColor={groupCountColor(registeredAgents)}
              forceCollapsed={!!selectedEventId}>
              {registeredAgents.length === 0 && <EmptyLabel>No active agents</EmptyLabel>}

              {/* Event-bound squads */}
              {Array.from(squadGroups.entries()).map(([eventId, squadAgents]) => {
                const event = events.find(e => e.id === eventId) || recentClosed.find(e => e.id === eventId);

                return (
                  <TreeGroup
                    key={eventId}
                    nested
                    icon={<Users size={14} className="text-accent" />}
                    label={squadLabelFor(eventId, event?.service)}
                    count={squadAgents.length}
                    countColor={groupCountColor(squadAgents)}
                  >
                    {sortAgents(squadAgents).map(renderAgentNode)}
                  </TreeGroup>
                );
              })}

              {/* Sensors and on-call sweep agents */}
              {sensorAgents.length > 0 && (
                <TreeGroup
                  nested
                  icon={<Radar size={14} className="text-cyan-400" />}
                  label="Sensors & On-Call"
                  count={sensorAgents.length}
                  countColor={groupCountColor(sensorAgents)}
                >
                  {sortAgents(sensorAgents).map(renderAgentNode)}
                </TreeGroup>
              )}

              {/* Standalone (non-event, non-sensor) agents */}
              {standaloneAgents.length > 0 && (
                squadGroups.size > 0 || sensorAgents.length > 0 ? (
                  <TreeGroup
                    nested
                    icon={<Bot size={14} className="text-text-muted" />}
                    label="Standalone"
                    count={standaloneAgents.length}
                    countColor={groupCountColor(standaloneAgents)}
                  >
                    {sortAgents(standaloneAgents).map(renderAgentNode)}
                  </TreeGroup>
                ) : (
                  sortAgents(standaloneAgents).map(renderAgentNode)
                )
              )}
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

            {/* ArgoCD Queue Group */}
            <TreeGroup icon={<SourceIcon source="aligner" evidence={{ argocd_app: "true" }} size={16} />}
              label="ArgoCD Queue" count={alignerPending.length}
              countColor={alignerPending.length > 0 ? '#EF7B4D' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {alignerPending.length === 0 && <EmptyLabel>No pending anomalies</EmptyLabel>}
              {alignerPending.map(item => (
                <TreeNode key={item.key}
                  icon={<SourceIcon source="aligner" evidence={{ argocd_app: item.argocd_app }} size={18} />}
                  label={item.target}
                  sublabel={`${item.anomaly_type} (${Math.floor((Date.now() / 1000 - item.first_seen) / 60)}m)`}
                  sublabelColor={item.severity === 'critical' ? '#ef4444' : '#f59e0b'}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: alignerPendingMenuItems(item) });
                  }}
                />
              ))}
            </TreeGroup>

            {/* Jenkins CI Queue Group */}
            <TreeGroup icon={<JenkinsIcon size={16} />}
              label="Jenkins Queue" count={jenkinsPending.length}
              countColor={jenkinsPending.length > 0 ? '#D33833' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {jenkinsPending.length === 0 && <EmptyLabel>No pending CI signals</EmptyLabel>}
              {jenkinsPending.map(item => (
                <TreeNode key={item.key}
                  icon={<JenkinsIcon size={18} />}
                  label={item.target}
                  sublabel={`${item.result || 'missing'} (${Math.floor((Date.now() / 1000 - item.first_seen) / 60)}m)`}
                  sublabelColor={item.result === 'FAILURE' ? '#ef4444' : '#f59e0b'}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setCtxMenu({ x: e.clientX, y: e.clientY, items: jenkinsQueueMenuItems(item) });
                  }}
                />
              ))}
            </TreeGroup>

            {/* HH Queue Group */}
            <TreeGroup icon={<GitMerge size={16} />} label="Headhunter Queue" count={demoHH.length}
              countColor={demoHH.length > 0 ? '#f59e0b' : '#64748b'}
              forceCollapsed={!!selectedEventId}>
              {hhError && <EmptyLabel>Failed to load queue</EmptyLabel>}
              {!hhError && demoHH.length === 0 && <EmptyLabel>No pending todos</EmptyLabel>}
              {demoHH.map((todo, idx) => {
                const isGitHub = isGitHubTodo(todo);
                return (
                  <TreeNode
                    key={getHeadhunterItemKey(todo, idx)}
                    icon={<SourceIcon source={isGitHub ? 'github' : 'headhunter'} size={18} />}
                    label={formatHeadhunterLabel(todo)}
                    sublabel={todo.action?.replace(/_/g, ' ') || ''}
                    sublabelColor={todo.pipeline_status === 'failed' ? '#ef4444' : '#64748b'}
                    onClick={() => safeOpen(todo.target_url)}
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setCtxMenu({ x: e.clientX, y: e.clientY, items: hhMenuItems(todo) });
                    }}
                  />
                );
              })}
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

