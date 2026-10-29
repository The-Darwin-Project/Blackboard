// BlackBoard/ui/src/components/workspace/WorkspaceInspector.tsx
// @ai-rules:
// 1. [Constraint]: Derive conversation/diffs inside useMemo keyed on eventDoc?.conversation; never create a fresh [] before the memo.
// 2. [Pattern]: Hooks run before the isOpen early return.
// 3. [Gotcha]: DOMAIN_COLORS is indexed via Object.hasOwn on the lowercased domain so prototype keys and unknown domains fall back to casual.
/**
 * Collapsible & resizable right sidebar for Agent Workspace.
 * Hosts Plan execution, Diff viewer, Swarm topology, Live Logs tabs, and Session Telemetry.
 */
import { useState, useMemo } from 'react';
import { ListTodo, GitCompare, Users, Terminal, X, ChevronDown, ChevronRight, Zap } from 'lucide-react';
import { useResizablePanel } from '../../hooks/useResizablePanel';
import { useEventDocument } from '../../hooks/useQueue';
import PlanProgress, { usePlanState } from '../PlanProgress';
import WorkspaceDiffViewer from './WorkspaceDiffViewer';
import WorkspaceSwarmPanel from './WorkspaceSwarmPanel';
import ActivityStream from '../ActivityStream';
import SourceIcon from '../SourceIcon';
import CiContextCard from '../CiContextCard';
import { extractDiffsFromConversation } from './diffParser';
import { STATUS_COLORS, DOMAIN_COLORS } from '../../constants/colors';
import { formatTokenCount } from '../../utils/formatTokens';
import type { ConversationTurn, TokenUsageDict, EventEvidence, CiContext } from '../../api/types';

interface WorkspaceInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  selectedEventId: string | null;
}

type TabType = 'plan' | 'diffs' | 'swarm' | 'logs';

const TOKEN_SEGMENTS: { key: keyof TokenUsageDict; label: string; color: string }[] = [
  { key: 'input_tokens', label: 'In', color: '#34d399' },
  { key: 'output_tokens', label: 'Out', color: '#f472b6' },
  { key: 'thinking_tokens', label: 'Think', color: '#a78bfa' },
  { key: 'cached_tokens', label: 'Cache', color: '#fbbf24' },
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

  const { size: width, isResizing, startResize, panelRef } = useResizablePanel({
    direction: 'horizontal', anchor: 'right', min: 300, max: 700, defaultSize: 420,
    storageKey: 'darwin:workspaceInspectorWidth', enabled: isOpen,
  });

  const { data: eventDoc } = useEventDocument(selectedEventId);
  const rawConversation = eventDoc?.conversation as ConversationTurn[] | undefined;
  const conversation = useMemo<ConversationTurn[]>(() => rawConversation ?? [], [rawConversation]);
  const diffs = useMemo(() => extractDiffsFromConversation(conversation), [conversation]);
  const { hasPlan, steps: planSteps } = usePlanState(conversation);

  const eventEvidence = eventDoc?.event?.evidence as EventEvidence | undefined;
  const brainDomain = (eventEvidence?.brain_domain || 'casual').toLowerCase();
  const domainColor = Object.hasOwn(DOMAIN_COLORS, brainDomain)
    ? DOMAIN_COLORS[brainDomain as keyof typeof DOMAIN_COLORS]
    : DOMAIN_COLORS.casual;
  const statusColor = STATUS_COLORS[eventDoc?.status || 'active'] || { bg: '#1e293b', text: '#94a3b8' };
  const userTrigger = eventEvidence?.triggered_by || eventDoc?.created_by_email;

  if (!isOpen) return null;

  return (
    <aside ref={panelRef} className="flex-shrink-0 bg-bg-secondary border-l border-border h-full flex flex-col relative select-none" style={{ width }}>
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
            <span>Plan{hasPlan && ` (${planSteps.filter(s => s.status === 'completed').length}/${planSteps.length})`}</span>
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
              <span className="truncate">{eventDoc.service || eventDoc.id || 'Session Overview'}</span>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span
                className="px-1.5 py-0.2 rounded text-[10px] font-medium"
                style={{ background: statusColor.bg, color: statusColor.text }}
              >
                {eventDoc.status}
              </span>
              <span
                className="px-1.5 py-0.2 rounded text-[10px] uppercase font-mono font-bold tracking-wider"
                style={{ background: `${domainColor.text}18`, color: domainColor.text, border: `1px solid ${domainColor.border}50` }}
              >
                {brainDomain}
              </span>
            </div>
          </button>

          {isOverviewOpen && (
            <div className="px-3 pb-2.5 pt-1 space-y-2 text-[11px]">
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
            <PlanProgress conversation={conversation} />
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
        {activeTab === 'swarm' && <WorkspaceSwarmPanel />}
        {activeTab === 'logs' && <ActivityStream />}
      </div>
    </aside>
  );
}

