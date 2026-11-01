// BlackBoard/ui/src/components/workspace/WorkspaceSessionsHub.tsx
// @ai-rules:
// 1. [Constraint]: Only evict selectedEventId if it was previously OBSERVED in the active, waiting_approval or closed lists and has since
//    disappeared from ALL three. A newly created / deep-linked ID is absent from a stale cache; evicting it would bounce the user to /workspace.
// 2. [Pattern]: Eviction calls onNewTask (WorkspaceLayout.handleDeselectEvent uses replace:true so Back is not trapped).
// 3. [Gotcha]: Eviction is skipped while ANY of the 3 sources (active, waiting_approval, closed) is loading, fetching, errored or has no data yet
//    (isLoading* / isFetching* / isError* / data === undefined). A failed poll or in-flight refetch yields stale/empty lists and must never evict.
// 4. [Pattern]: Scoping: 'mine' vs 'all' (Global) is a CLIENT-SIDE workspace view filter only (not an authz boundary; the API returns the same lists).
//    'mine' matches the OIDC email or preferred_username against created_by_email / evidence.triggered_by.
//    The project filter exists ONLY in Global mode (scope === 'all') and is reset to 'all' when toggling to My Tasks.
//    Project is derived from evidence.project, then gitlab_context.project, github_context.repo, kargo_context.project (trimmed).
//    A selected project that leaves availableProjects falls back to 'all' (effectiveProject).
// 5. [Pattern]: Accordion folders: Waiting for Approval (shown in Global, or in My Tasks only when non-empty), Active, Deferred, and
//    Closed & Failed (defaults collapsed). An event renders in exactly one folder: waiting rows are dropped when the id is in closed or is
//    in active with a non-waiting status (stale waiting cache); waiting rows are sorted deterministically (created desc, then id).
/**
 * Collapsible left panel for task session switching in Agent Workspace.
 * Supports dual-scope filtering ('My Tasks' vs 'Global'), a Global-only project filter,
 * and collapsible folders for Waiting for Approval, Active, Deferred, and Closed/Failed tasks.
 */
import { useEffect, useRef, useState, useMemo } from 'react';
import { Plus, ChevronDown, ChevronRight, Activity, Clock, CheckCircle2, User, Globe, Filter, AlertCircle } from 'lucide-react';
import { useActiveEvents, useClosedEvents, useWaitingApprovalEvents } from '../../hooks/useQueue';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useOpsControl } from '../../contexts/OpsStateContext';
import { useAuth } from '../../contexts/AuthContext';
import WorkspaceTaskItem from './WorkspaceTaskItem';
import type { ActiveEvent } from '../../api/types';

const EMPTY_EVENTS: ActiveEvent[] = [];

const createdMs = (evt: ActiveEvent): number => {
  const t = Date.parse(evt.created);
  return Number.isNaN(t) ? 0 : t;
};

const asTrimmed = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

/** Project an event belongs to, tolerant of both evidence.project and backend context payloads. */
function deriveProject(evt: ActiveEvent): string {
  if (!evt) return '';
  const ev = evt.evidence;
  return (
    asTrimmed(ev?.project)
    || asTrimmed(ev?.gitlab_context?.project)
    || asTrimmed(ev?.github_context?.repo)
    || asTrimmed(ev?.kargo_context?.project)
  );
}

interface WorkspaceSessionsHubProps {
  isOpen: boolean;
  selectedEventId?: string | null;
  onSelectEvent?: (eventId: string) => void;
  onNewTask: () => void;
}

export default function WorkspaceSessionsHub({
  isOpen,
  selectedEventId: propSelectedEventId,
  onSelectEvent: propOnSelectEvent,
  onNewTask,
}: WorkspaceSessionsHubProps) {
  const {
    data: activeData, isLoading: isLoadingActive, isFetching: isFetchingActive, isError: isErrorActive,
  } = useActiveEvents();
  const {
    data: closedData, isLoading: isLoadingClosed, isFetching: isFetchingClosed, isError: isErrorClosed,
  } = useClosedEvents(50);
  const {
    data: waitingData, isLoading: isLoadingWaiting, isFetching: isFetchingWaiting, isError: isErrorWaiting,
  } = useWaitingApprovalEvents();
  const rawActiveEvents = activeData ?? EMPTY_EVENTS;
  const rawClosedEvents = closedData ?? EMPTY_EVENTS;
  const rawWaitingApprovalEvents = waitingData ?? EMPTY_EVENTS;
  const opsControl = useOpsControl();
  const { user } = useAuth();

  const selectedEventId = propSelectedEventId !== undefined ? propSelectedEventId : opsControl.selectedEventId;

  // Identity resolution for scoping: either the email or the username claim may match the creator.
  const profileEmail = asTrimmed(user?.profile?.email).toLowerCase();
  const profileUsername = asTrimmed(user?.profile?.preferred_username).toLowerCase();

  // Scoping and filter state
  const [scope, setScope] = useState<'mine' | 'all'>('mine');
  const [selectedProject, setSelectedProject] = useState<string>('all');

  // Accordion open/close state
  const [waitingApprovalOpen, setWaitingApprovalOpen] = useState(true);
  const [activeOpen, setActiveOpen] = useState(true);
  const [deferredOpen, setDeferredOpen] = useState(true);
  const [closedOpen, setClosedOpen] = useState(false); // Default collapsed per design

  // Distinct projects derived from all active + closed + waiting_approval events
  const availableProjects = useMemo(() => {
    const set = new Set<string>();
    [...rawActiveEvents, ...rawClosedEvents, ...rawWaitingApprovalEvents].forEach(evt => {
      const proj = deriveProject(evt);
      if (proj) set.add(proj);
    });
    return Array.from(set).sort();
  }, [rawActiveEvents, rawClosedEvents, rawWaitingApprovalEvents]);

  // A selection whose project vanished from the lists resets to 'all' instead of hiding everything
  const effectiveProject =
    selectedProject === 'all' || availableProjects.includes(selectedProject) ? selectedProject : 'all';

  // Categorize events
  const { waitingApprovalTasks, activeTasks, deferredTasks, closedTasks } = useMemo(() => {
    const matchesUser = (evt: ActiveEvent): boolean => {
      if (!profileEmail && !profileUsername) return true; // fallback if no auth profile loaded
      const owners = [evt.created_by_email, evt.evidence?.triggered_by].map(o => asTrimmed(o).toLowerCase());
      return owners.some(o => o !== '' && (o === profileEmail || o === profileUsername));
    };
    const matchesProject = (evt: ActiveEvent): boolean =>
      scope === 'mine' || effectiveProject === 'all' || deriveProject(evt) === effectiveProject;
    const filterFn = (evt: ActiveEvent) => (scope !== 'mine' || matchesUser(evt)) && matchesProject(evt);

    // Identity-level dedup against the UNFILTERED lists so one event never renders in two folders:
    // closed wins over waiting, and a non-waiting active row wins over a stale waiting cache entry.
    const closedIds = new Set(rawClosedEvents.map(e => e.id));
    const activeNonWaitingIds = new Set(
      rawActiveEvents.filter(e => e.status !== 'waiting_approval').map(e => e.id),
    );
    const isSupersededWaiting = (id: string) => closedIds.has(id) || activeNonWaitingIds.has(id);

    const waitingById = new Map<string, ActiveEvent>();
    [...rawWaitingApprovalEvents, ...rawActiveEvents.filter(e => e.status === 'waiting_approval')].forEach(evt => {
      if (!filterFn(evt) || isSupersededWaiting(evt.id) || waitingById.has(evt.id)) return;
      waitingById.set(evt.id, evt);
    });
    const waiting = Array.from(waitingById.values()).sort(
      (a, b) => createdMs(b) - createdMs(a) || a.id.localeCompare(b.id),
    );

    const active: ActiveEvent[] = [];
    const deferred: ActiveEvent[] = [];
    rawActiveEvents.forEach(evt => {
      if (!filterFn(evt) || evt.status === 'waiting_approval') return;
      if (evt.status === 'deferred') deferred.push(evt);
      else active.push(evt);
    });

    const closed = rawClosedEvents.filter(filterFn);

    return {
      waitingApprovalTasks: waiting,
      activeTasks: active,
      deferredTasks: deferred,
      closedTasks: closed,
    };
  }, [rawActiveEvents, rawClosedEvents, rawWaitingApprovalEvents, scope, effectiveProject, profileEmail, profileUsername]);

  // Eviction tracking: check against UNFILTERED raw events to prevent filtering from kicking the user out
  const seenIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Any source still loading/refetching, failed, or never delivered data => lists may be stale or empty; never evict or record.
    if (isLoadingActive || isLoadingClosed || isLoadingWaiting) return;
    if (isFetchingClosed || isFetchingWaiting) return;
    if (isErrorActive || isErrorClosed || isErrorWaiting) return;
    if (activeData === undefined || closedData === undefined || waitingData === undefined) return;
    const seen = seenIdsRef.current;
    const allCurrentRawIds = new Set([
      ...rawActiveEvents.map(e => e.id),
      ...rawClosedEvents.map(e => e.id),
      ...rawWaitingApprovalEvents.map(e => e.id),
    ]);

    if (selectedEventId && seen.has(selectedEventId) && !allCurrentRawIds.has(selectedEventId)) {
      if (isFetchingActive) return;
      seen.delete(selectedEventId);
      onNewTask();
      return;
    }

    allCurrentRawIds.forEach(id => seen.add(id));
  }, [
    rawActiveEvents,
    rawClosedEvents,
    rawWaitingApprovalEvents,
    isLoadingActive,
    isLoadingClosed,
    isLoadingWaiting,
    isFetchingActive,
    isFetchingClosed,
    isFetchingWaiting,
    isErrorActive,
    isErrorClosed,
    isErrorWaiting,
    activeData,
    closedData,
    waitingData,
    selectedEventId,
    onNewTask,
  ]);

  const handleSelect = (id: string) => {
    if (propOnSelectEvent) {
      propOnSelectEvent(id);
    } else {
      opsControl.selectEvent(id);
    }
  };

  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', min: 240, max: 480, defaultSize: 300,
    storageKey: 'darwin:workspaceSessionsWidth', enabled: isOpen,
  });

  if (!isOpen) return null;

  return (
    <aside ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-r border-border h-full flex flex-col relative" style={{ width }}>
      {/* Top Header: New Task + Title */}
      <div className="p-3 border-b border-border flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-primary tracking-wider uppercase">Workspace</span>
        <button
          onClick={onNewTask}
          aria-label="New Task"
          className="flex items-center gap-1.5 px-2 py-1 rounded bg-accent/15 border border-accent/30 hover:bg-accent/25 text-accent text-xs font-medium transition-colors"
          title="Create New Task"
        >
          <Plus size={13} />
          <span>New Task</span>
        </button>
      </div>

      {/* Scope Segmented Control: My Workspace vs Global */}
      <div className="p-2 border-b border-border/60 bg-bg-tertiary/20 flex flex-col gap-2">
        <div className="grid grid-cols-2 p-0.5 rounded-md bg-bg-tertiary/60 border border-border/40 text-xs">
          <button
            onClick={() => {
              setScope('mine');
              setSelectedProject('all');
            }}
            className={`flex items-center justify-center gap-1.5 py-1 px-2 rounded font-medium transition-colors ${
              scope === 'mine'
                ? 'bg-bg-primary text-text-primary shadow-xs'
                : 'text-text-muted hover:text-text-secondary'
            }`}
            title="Show tasks triggered by you"
          >
            <User size={12} />
            <span>My Tasks</span>
          </button>
          <button
            onClick={() => setScope('all')}
            className={`flex items-center justify-center gap-1.5 py-1 px-2 rounded font-medium transition-colors ${
              scope === 'all'
                ? 'bg-bg-primary text-text-primary shadow-xs'
                : 'text-text-muted hover:text-text-secondary'
            }`}
            title="Show all cluster and automated tasks"
          >
            <Globe size={12} />
            <span>Global</span>
          </button>
        </div>

        {/* Project Selector (shown in Global view when projects exist) */}
        {scope === 'all' && availableProjects.length > 0 && (
          <div className="flex items-center gap-1.5 px-1 text-xs text-text-muted">
            <Filter size={11} className="flex-shrink-0" />
            <select
              value={effectiveProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full bg-bg-primary border border-border/50 rounded px-1.5 py-0.5 text-xs text-text-secondary focus:outline-none focus:border-accent"
              aria-label="Filter by project"
            >
              <option value="all">All Repositories / Projects</option>
              {availableProjects.map(proj => (
                <option key={proj} value={proj}>{proj}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Accordion Lists */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {(isLoadingActive || isLoadingClosed || isLoadingWaiting) && (
          <div className="p-4 text-center text-xs text-text-muted animate-pulse">Loading tasks...</div>
        )}

        {/* 1. Waiting for Approval Tasks Folder (Global View or when present in personal tasks) */}
        {(scope === 'all' || waitingApprovalTasks.length > 0) && (
          <div className="space-y-1">
            <button
              onClick={() => setWaitingApprovalOpen(v => !v)}
              aria-expanded={waitingApprovalOpen}
              className="w-full flex items-center justify-between px-1.5 py-1 text-xs font-semibold text-text-secondary hover:bg-bg-tertiary/50 rounded transition-colors"
            >
              <div className="flex items-center gap-1.5">
                {waitingApprovalOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                <AlertCircle size={13} className="text-amber-400" />
                <span>Waiting for Approval</span>
              </div>
              <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-normal">
                {waitingApprovalTasks.length}
              </span>
            </button>

            {waitingApprovalOpen && (
              <div className="pl-1 space-y-1">
                {waitingApprovalTasks.length === 0 ? (
                  isLoadingActive || isLoadingWaiting ? null : <div className="py-2 px-3 text-[11px] text-text-muted/70 italic">No tasks waiting for approval</div>
                ) : (
                  waitingApprovalTasks.map((evt) => (
                    <WorkspaceTaskItem
                      key={evt.id}
                      evt={evt}
                      isSelected={evt.id === selectedEventId}
                      onSelect={handleSelect}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {/* 2. Active Tasks Folder */}
        <div className="space-y-1">
          <button
            onClick={() => setActiveOpen(v => !v)}
            aria-expanded={activeOpen}
            className="w-full flex items-center justify-between px-1.5 py-1 text-xs font-semibold text-text-secondary hover:bg-bg-tertiary/50 rounded transition-colors"
          >
            <div className="flex items-center gap-1.5">
              {activeOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <Activity size={13} className="text-emerald-400" />
              <span>Active</span>
            </div>
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-normal">
              {activeTasks.length}
            </span>
          </button>

          {activeOpen && (
            <div className="pl-1 space-y-1">
              {activeTasks.length === 0 ? (
                isLoadingActive ? null : <div className="py-2 px-3 text-[11px] text-text-muted/70 italic">No active tasks</div>
              ) : (
                activeTasks.map((evt) => (
                  <WorkspaceTaskItem
                    key={evt.id}
                    evt={evt}
                    isSelected={evt.id === selectedEventId}
                    onSelect={handleSelect}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* 3. Deferred Tasks Folder */}
        <div className="space-y-1">
          <button
            onClick={() => setDeferredOpen(v => !v)}
            aria-expanded={deferredOpen}
            className="w-full flex items-center justify-between px-1.5 py-1 text-xs font-semibold text-text-secondary hover:bg-bg-tertiary/50 rounded transition-colors"
          >
            <div className="flex items-center gap-1.5">
              {deferredOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <Clock size={13} className="text-violet-400" />
              <span>Deferred</span>
            </div>
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 font-normal">
              {deferredTasks.length}
            </span>
          </button>

          {deferredOpen && (
            <div className="pl-1 space-y-1">
              {deferredTasks.length === 0 ? (
                isLoadingActive ? null : <div className="py-2 px-3 text-[11px] text-text-muted/70 italic">No deferred tasks</div>
              ) : (
                deferredTasks.map((evt) => (
                  <WorkspaceTaskItem
                    key={evt.id}
                    evt={evt}
                    isSelected={evt.id === selectedEventId}
                    onSelect={handleSelect}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* 4. Closed & Failed Tasks Folder (Default Collapsed) */}
        <div className="space-y-1">
          <button
            onClick={() => setClosedOpen(v => !v)}
            aria-expanded={closedOpen}
            className="w-full flex items-center justify-between px-1.5 py-1 text-xs font-semibold text-text-secondary hover:bg-bg-tertiary/50 rounded transition-colors"
          >
            <div className="flex items-center gap-1.5">
              {closedOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <CheckCircle2 size={13} className="text-text-muted" />
              <span>Closed &amp; Failed</span>
            </div>
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded-full bg-slate-500/10 text-text-muted font-normal">
              {closedTasks.length}
            </span>
          </button>

          {closedOpen && (
            <div className="pl-1 space-y-1">
              {closedTasks.length === 0 ? (
                isLoadingClosed ? null : <div className="py-2 px-3 text-[11px] text-text-muted/70 italic">No closed tasks</div>
              ) : (
                closedTasks.map((evt) => (
                  <WorkspaceTaskItem
                    key={evt.id}
                    evt={evt}
                    isSelected={evt.id === selectedEventId}
                    onSelect={handleSelect}
                  />
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Resize Handle */}
      <div className={`absolute top-0 right-0 w-1.5 h-full cursor-col-resize group ${isResizing ? 'bg-accent/40' : ''}`} onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>
    </aside>
  );
}
