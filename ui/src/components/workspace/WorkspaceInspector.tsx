// BlackBoard/ui/src/components/workspace/WorkspaceInspector.tsx
// @ai-rules:
// 1. [Constraint]: Derive conversation/diffs inside useMemo keyed on eventDoc?.conversation; never create a fresh [] before the memo.
// 2. [Pattern]: Hooks run before the isOpen early return.
// 3. [Gotcha]: DOMAIN_COLORS is indexed via Object.hasOwn on the lowercased domain so prototype keys and unknown domains fall back to casual.
// 4. [Pattern]: Hoists FloatingWindow for agent message streams across tab transitions (Plan <-> Swarm <-> Logs).
// 5. [Pattern]: Ambient activity beacon in Plan tab header when agents are active for selectedEventId.
// 6. [Constraint]: activeAgentRoles counts only stream.isActive (not buffered messages) and busy ops agents; stream lookup matches
//    on stream.actor / stream.eventId, never by splitting the 'actor:eventId' key.
/**
 * Collapsible & resizable right sidebar for Agent Workspace.
 * Hosts Plan execution, Diff viewer, Swarm topology, Live Logs tabs, and Session Telemetry.
 */
import { useState, useMemo, useEffect } from 'react';
import { ListTodo, GitCompare, Users, Terminal, X, ChevronDown, ChevronRight, Zap, Pencil } from 'lucide-react';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useEventDocument } from '../../hooks/useQueue';
import { useOpsControlSafe } from '../../contexts/OpsStateContext';
import { useActiveStreamsSafe } from '../../contexts/activeStreamsStore';
import { updateEventTitle } from '../../api/client';
import PlanProgress from '../PlanProgress';
import { usePlanState } from '../../hooks/usePlanState';
import { canonicalRole } from '../../utils/planState';
import WorkspaceDiffViewer from './WorkspaceDiffViewer';
import WorkspaceSwarmPanel from './WorkspaceSwarmPanel';
import ActivityStream from '../ActivityStream';
import SourceIcon from '../SourceIcon';
import CiContextCard from '../CiContextCard';
import FloatingWindow from './FloatingWindow';
import { extractDiffsFromConversation } from './diffParser';
import { STATUS_COLORS, DOMAIN_COLORS } from '../../constants/colors';
import { formatTokenCount } from '../../utils/formatTokens';
import CopyButton from './CopyButton';
import type { ConversationTurn, TokenUsageDict, EventEvidence, CiContext } from '../../api/types';

interface WorkspaceInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selectedEventId: string | null;
}

type TabType = 'plan' | 'diffs' | 'swarm' | 'logs';

const EMPTY_MESSAGES: string[] = [];

const TOKEN_SEGMENTS: { key: keyof TokenUsageDict; label: string; color: string }[] = [
  { key: 'input_tokens', label: 'In', color: '#34d399' },
  { key: 'output_tokens', label: 'Out', color: '#f472b6' },
  { key: 'thinking_tokens', label: 'Think', color: '#a78bfa' },
  { key: 'cached_tokens', label: 'Cache', color: '#fbbf24' },
  { key: 'tool_use_tokens', label: 'Tools', color: '#38bdf8' },
];

function SessionTokenUsageMini({ usage, isLive }: { usage: TokenUsageDict; isLive: boolean }) {
  const total = usage.total_tokens || 0;
  return (
    <div className="pt-2 border-t border-border/40 space-y-1.5">
      <div className="flex justify-between items-center text-[11px]">
        <span className="text-text-muted flex items-center gap-1 font-medium">
          <Zap size={11} className="text-accent" /> Tokens
          {isLive && <span className="text-emerald-400 text-[9px] font-semibold">live</span>}
        </span>
        <span className="font-mono text-blue-400 font-semibold">{formatTokenCount(total)}</span>
      </div>
      {total > 0 && (
        <>
          <div className="flex h-1.5 rounded-full overflow-hidden bg-bg-tertiary">
            {TOKEN_SEGMENTS.map(({ key, color }) => {
              const val = usage[key] || 0;
              const pct = (val / total) * 100;
              return pct > 0 ? <div key={key} style={{ width: `${pct}%`, background: color }} /> : null;
            })}
          </div>
          <div className="flex flex-wrap gap-x-2.5 gap-y-1">
            {TOKEN_SEGMENTS.map(({ key, label, color }) => {
              const val = usage[key] || 0;
              if (!val) return null;
              return (
                <span key={key} className="text-[10px] flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: color }} />
                  <span className="text-text-muted">{label}</span>
                  <span className="font-mono" style={{ color }}>{formatTokenCount(val)}</span>
                </span>
              );
            })}
            {(usage.calls || 0) > 0 && (
              <span className="text-[10px] text-text-muted">
                {usage.calls} calls
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function WorkspaceInspector({ isOpen, onClose, selectedEventId }: WorkspaceInspectorProps) {
  const [activeTab, setActiveTab] = useState<TabType>('plan');
  const [isOverviewOpen, setIsOverviewOpen] = useState(true);
  const [floatingTarget, setFloatingTarget] = useState<{ agentName: string; eventId: string } | null>(null);

  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', anchor: 'right', min: 300, max: 700, defaultSize: 420,
    storageKey: 'darwin:workspaceInspectorWidth', enabled: isOpen,
  });

  const opsControl = useOpsControlSafe();
  const { activeStreams } = useActiveStreamsSafe();

  const { data: eventDoc } = useEventDocument(selectedEventId);
  const rawConversation = eventDoc?.conversation as ConversationTurn[] | undefined;
  const conversation = useMemo<ConversationTurn[]>(() => rawConversation ?? [], [rawConversation]);
  const diffs = useMemo(() => extractDiffsFromConversation(conversation), [conversation]);
  const { hasPlan, steps: planSteps } = usePlanState(conversation);

  const eventEvidence = eventDoc?.event?.evidence as EventEvidence | undefined;
  const brainDomain = (eventEvidence?.brain_domain || eventEvidence?.domain || 'disorder').toLowerCase();
  const domainColor = Object.hasOwn(DOMAIN_COLORS, brainDomain)
    ? DOMAIN_COLORS[brainDomain as keyof typeof DOMAIN_COLORS]
    : DOMAIN_COLORS.casual;
  const statusColor = STATUS_COLORS[eventDoc?.status || 'active'] || { bg: '#1e293b', text: '#94a3b8' };
  const userTrigger = eventEvidence?.triggered_by || eventDoc?.created_by_email;

  // Auto-close floating stream window if selected event changes or closes
  useEffect(() => {
    if (floatingTarget && floatingTarget.eventId !== selectedEventId) {
      setFloatingTarget(null);
    }
  }, [selectedEventId, floatingTarget]);

  // Compute active agent roles for selectedEventId
  const activeAgentRoles = useMemo(() => {
    const roles = new Set<string>();
    if (!selectedEventId) return roles;

    // 1. From activeStreams
    if (activeStreams) {
      Object.values(activeStreams).forEach((stream) => {
        // Only a live stream counts: applyTurn flips isActive=false when the agent's turn lands, while
        // the buffered messages remain (for the floating log window) and must not keep the beacon lit.
        if (stream && stream.eventId === selectedEventId && stream.isActive) {
          const r = canonicalRole(stream.actor);
          if (r) roles.add(r);
        }
      });
    }

    // 2. From opsControl.agents
    if (opsControl?.agents) {
      opsControl.agents.forEach((agent) => {
        if (agent.bound_event_id === selectedEventId && agent.busy) {
          const rawRole = agent.current_role || agent.role || agent.agent_id || '';
          const r = canonicalRole(rawRole);
          if (r) roles.add(r);
        }
      });
    }

    return roles;
  }, [selectedEventId, activeStreams, opsControl?.agents]);

  // Resolve messages for floatingTarget (case-insensitive stream key matching)
  const floatingMessages = useMemo(() => {
    if (!floatingTarget || !activeStreams) return EMPTY_MESSAGES;
    const targetAgent = canonicalRole(floatingTarget.agentName);
    const targetEvent = (floatingTarget.eventId || '').toLowerCase();

    const stream = Object.values(activeStreams).find((s) =>
      !!s &&
      canonicalRole(s.actor) === targetAgent &&
      (s.eventId || '').toLowerCase() === targetEvent,
    );

    return stream?.messages ?? EMPTY_MESSAGES;
  }, [floatingTarget, activeStreams]);

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState('');
  const [isSubmittingTitle, setIsSubmittingTitle] = useState(false);
  const [titleError, setTitleError] = useState<string | null>(null);

  const startEditingTitle = () => {
    setDraftTitle(eventDoc?.title || '');
    setTitleError(null);
    setIsEditingTitle(true);
  };

  const handleTitleKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (isSubmittingTitle) return;
      const clean = draftTitle.trim().replace(/\s+/g, ' ');
      if (clean && clean !== eventDoc?.title && eventDoc?.id) {
        setIsSubmittingTitle(true);
        setTitleError(null);
        try {
          await updateEventTitle(eventDoc.id, clean);
          setIsEditingTitle(false);
        } catch (err) {
          console.error('Failed to update event title in inspector:', err);
          setTitleError('Failed to rename');
        } finally {
          setIsSubmittingTitle(false);
        }
      } else {
        setIsEditingTitle(false);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (isSubmittingTitle) return;
      setTitleError(null);
      setIsEditingTitle(false);
    }
  };

  if (!isOpen) return null;

  return (
    <aside ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-l border-border h-full flex flex-col relative" style={{ width }}>
      <div className="absolute top-0 left-0 w-1.5 h-full cursor-col-resize group" onMouseDown={startResize}>
        <div className={`w-px h-full mx-auto transition-colors ${isResizing ? 'bg-accent' : 'bg-transparent group-hover:bg-accent/40'}`} />
      </div>

      {/* Top Bar with Navigation Tabs and Close Action */}
      <div className="flex-shrink-0 px-3 py-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-1 bg-bg-tertiary p-0.5 rounded-lg text-xs">
          <button
            onClick={() => setActiveTab('plan')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === 'plan' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            <ListTodo size={13} />
            <span>
              Plan
              {hasPlan && ` (${planSteps.filter(s => s.status === 'completed' || s.status === 'green_verified').length}/${planSteps.length})`}
            </span>
            {activeAgentRoles.size > 0 && (
              <span
                data-testid="plan-tab-activity-beacon"
                className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5"
                title="Active agent working on plan"
              />
            )}
          </button>
          <button
            onClick={() => setActiveTab('diffs')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === 'diffs' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            <GitCompare size={13} />
            <span>Diffs{diffs.length > 0 && ` (${diffs.length})`}</span>
          </button>
          <button
            onClick={() => setActiveTab('swarm')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === 'swarm' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            <Users size={13} />
            <span>Swarm</span>
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === 'logs' ? 'bg-bg-primary text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            <Terminal size={13} />
            <span>Logs</span>
          </button>
        </div>
        <button
          onClick={onClose}
          aria-label="Close Inspector"
          title="Close Inspector (Cmd+J)"
          className="p-1 rounded text-text-muted hover:text-text-secondary hover:bg-bg-tertiary transition-colors"
        >
          <X size={15} />
        </button>
      </div>

      {/* Pinned Collapsible Session Overview & Telemetry Card */}
      {eventDoc && (
        <div className="flex-shrink-0 border-b border-border/80 bg-bg-primary/50">
          <button
            onClick={() => setIsOverviewOpen(prev => !prev)}
            className="w-full px-3 py-1.5 flex items-center justify-between text-[11px] font-semibold text-text-secondary hover:bg-bg-tertiary/40 transition-colors"
          >
            <div className="flex items-center gap-1.5 truncate">
              {isOverviewOpen ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
              <span className="truncate">{eventDoc.title || eventDoc.service || eventDoc.id || 'Session Overview'}</span>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span
                className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                style={{ background: statusColor.bg, color: statusColor.text }}
              >
                {eventDoc.status}
              </span>
              <span
                className="px-1.5 py-0.5 rounded text-[10px] uppercase font-mono font-bold tracking-wider"
                style={{ background: `${domainColor.text}18`, color: domainColor.text, border: `1px solid ${domainColor.border}50` }}
              >
                {brainDomain}
              </span>
            </div>
          </button>

          {isOverviewOpen && (
            <div className="px-3 pb-2.5 pt-1 space-y-2 text-[11px]">
              <div className="flex items-center justify-between gap-1 text-text-muted">
                <span className="truncate font-mono" title={eventDoc.id}>{eventDoc.id}</span>
                <CopyButton text={eventDoc.id} label="Copy Event ID" iconSize={12} />
              </div>
              {isEditingTitle ? (
                <div className="flex items-center gap-1.5 bg-bg-tertiary/40 px-2 py-1 rounded border border-accent">
                  <input
                    type="text"
                    aria-label="Edit Event Title"
                    autoFocus
                    disabled={isSubmittingTitle}
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    onKeyDown={handleTitleKeyDown}
                    onBlur={() => {
                      if (!isSubmittingTitle) {
                        setTitleError(null);
                        setIsEditingTitle(false);
                      }
                    }}
                    className="text-[11px] font-mono bg-transparent text-text-primary outline-none flex-1 min-w-0"
                  />
                  {titleError && (
                    <span className="text-[9px] text-red-400 font-sans" role="alert">{titleError}</span>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-between gap-1.5 bg-bg-tertiary/40 px-2 py-1 rounded border border-border/50">
                  <span
                    onClick={startEditingTitle}
                    className="text-text-primary font-medium truncate text-[11px] cursor-pointer hover:underline"
                    title={eventDoc.title ? `${eventDoc.title} (Click to rename)` : 'Click to add title'}
                  >
                    {eventDoc.title || 'Untitled Event'}
                  </span>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {eventDoc.title_source && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] uppercase font-mono tracking-wider bg-bg-secondary text-text-muted border border-border/60">
                        {eventDoc.title_source}
                      </span>
                    )}
                    <button
                      onClick={startEditingTitle}
                      className="p-0.5 text-text-muted hover:text-text-secondary rounded hover:bg-bg-secondary transition-colors"
                      aria-label="Rename Event"
                      title="Rename Event"
                    >
                      <Pencil size={10} />
                    </button>
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-text-muted">
                {eventDoc.source && (
                  <div className="flex items-center gap-1 truncate">
                    <SourceIcon
                      source={eventDoc.source}
                      subjectType={eventDoc.subject_type}
                      evidence={eventEvidence as unknown as Record<string, unknown> | undefined}
                      size={13}
                    />
                    <span className="truncate">{eventDoc.source}</span>
                  </div>
                )}
                {userTrigger && (
                  <div className="truncate text-right" title={userTrigger}>
                    <span className="text-text-secondary truncate">{userTrigger}</span>
                  </div>
                )}
              </div>

              {/* CI Context if present */}
              {eventEvidence?.ci_context && (
                <div className="pt-1">
                  <CiContextCard context={eventEvidence.ci_context as CiContext} />
                </div>
              )}

              {/* Live Token Utilization */}
              {eventDoc.token_usage && (eventDoc.token_usage as TokenUsageDict).total_tokens > 0 && (
                <SessionTokenUsageMini
                  usage={eventDoc.token_usage as TokenUsageDict}
                  isLive={eventDoc.status !== 'closed'}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Main Tab View */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeTab === 'plan' && (
          hasPlan ? (
            <PlanProgress
              conversation={conversation}
              activeAgentRoles={activeAgentRoles}
              onOpenStream={(agentRole) => {
                if (selectedEventId) {
                  setFloatingTarget({ agentName: agentRole, eventId: selectedEventId });
                }
              }}
            />
          ) : (
            <div className="p-8 text-center text-text-muted text-xs space-y-2">
              <ListTodo size={24} className="mx-auto mb-2 opacity-40 text-text-muted" />
              <div className="font-medium text-text-secondary">No execution plan for this session</div>
              <p className="text-[11px] text-text-muted max-w-[260px] mx-auto leading-relaxed">
                Structured execution plans appear here when agents chalk multi-step remediation or task plans.
              </p>
            </div>
          )
        )}
        {activeTab === 'diffs' && <WorkspaceDiffViewer diffs={diffs} />}
        {activeTab === 'swarm' && <WorkspaceSwarmPanel selectedEventId={selectedEventId} />}
        {activeTab === 'logs' && <ActivityStream />}
      </div>

      {/* Hoisted Floating Window for live agent stream */}
      {floatingTarget && (
        <FloatingWindow
          agentName={floatingTarget.agentName}
          eventId={floatingTarget.eventId}
          messages={floatingMessages}
          onClose={() => setFloatingTarget(null)}
        />
      )}
    </aside>
  );
}
