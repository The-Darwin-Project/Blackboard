// BlackBoard/ui/src/components/JarvisMemoryPage.tsx
// @ai-rules:
// 1. [Pattern]: Page shell following 3-state pattern (loading, empty, populated).
// 2. [Pattern]: Fetches handoff reports + proposals on mount via TanStack Query.
// 3. [Pattern]: Live updates via WebSocket (cortex_handoff_report, cortex_proposal).
// 4. [Constraint]: Timeline cards newest-first. Handoff cards purple, proposal cards amber.
/**
 * JARVIS Memory page -- timeline of session handoff reports and enhancement proposals.
 */
import { useState, useCallback } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { Brain, ChevronDown, ChevronRight, Lightbulb, X } from 'lucide-react';
import { useWSMessage, useWSReconnect } from '../contexts/WebSocketContext';
import { getHandoffReports, getProposals, dismissProposals } from '../api/client';
import type { HandoffReport, EnhancementProposal } from '../api/client';

type FilterMode = 'all' | 'handoff' | 'proposals';

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(ts: number): string {
  return new Date(ts * 1000).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

const SEVERITY_COLORS: Record<string, string> = {
  blocking: 'bg-red-900/40 text-red-300',
  would_improve: 'bg-amber-900/40 text-amber-300',
  nice_to_have: 'bg-slate-700/60 text-slate-300',
};

function HandoffCard({ report }: { report: HandoffReport }) {
  const [expanded, setExpanded] = useState(false);
  const preview = report.report.length > 200 && !expanded
    ? report.report.slice(0, 200) + '…' : report.report;

  return (
    <div className="border-l-[3px] border-purple-500 pl-3 py-2">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[11px] text-text-muted">{formatDate(report.timestamp)} {formatTime(report.timestamp)}</span>
        <span className="text-xs font-semibold text-purple-400">Session Handoff</span>
        {report.events_tracked && (
          <span className="text-[11px] text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
            {report.events_tracked}
          </span>
        )}
      </div>
      <div className="text-[13px] text-text-secondary whitespace-pre-wrap">{preview}</div>
      {report.report.length > 200 && (
        <button onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-purple-400 hover:text-purple-300 mt-1 flex items-center gap-0.5">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  );
}

function ProposalCard({ proposal, onDismiss }: { proposal: EnhancementProposal; onDismiss?: (ts: number) => void }) {
  const [expanded, setExpanded] = useState(false);
  const preview = proposal.description.length > 200 && !expanded
    ? proposal.description.slice(0, 200) + '…' : proposal.description;

  return (
    <div className="border-l-[3px] border-amber-500 pl-3 py-2 group">
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className="text-[11px] text-text-muted">{formatDate(proposal.timestamp)} {formatTime(proposal.timestamp)}</span>
        <span className="text-xs font-semibold text-amber-400">Enhancement Proposal</span>
        <span className={`text-[11px] px-1.5 py-0.5 rounded ${SEVERITY_COLORS[proposal.severity] || SEVERITY_COLORS.nice_to_have}`}>
          {proposal.severity.replace('_', ' ')}
        </span>
        {proposal.event_id && (
          <span className="text-[11px] text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
            {proposal.event_id}
          </span>
        )}
        {onDismiss && (
          <button
            onClick={() => onDismiss(proposal.timestamp)}
            className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-[11px] text-text-muted hover:text-red-400 flex items-center gap-0.5 px-1.5 py-0.5 rounded hover:bg-red-900/20"
            title="Dismiss proposal"
          >
            <X className="w-3 h-3" /> Dismiss
          </button>
        )}
      </div>
      <div className="text-sm font-semibold text-text-primary mb-0.5">{proposal.title}</div>
      <div className="text-[13px] text-text-muted whitespace-pre-wrap">{preview}</div>
      {proposal.description.length > 200 && (
        <button onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-amber-400 hover:text-amber-300 mt-1 flex items-center gap-0.5">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  );
}

export default function JarvisMemoryPage() {
  const [filter, setFilter] = useState<FilterMode>('all');
  const queryClient = useQueryClient();

  const { data: reports, isLoading: reportsLoading } = useQuery({
    queryKey: ['jarvis-handoff-reports'],
    queryFn: getHandoffReports,
    staleTime: 30_000,
  });

  const { data: proposals, isLoading: proposalsLoading } = useQuery({
    queryKey: ['jarvis-proposals'],
    queryFn: getProposals,
    staleTime: 30_000,
  });

  const dismissMutation = useMutation({
    mutationFn: (timestamps: number[]) => dismissProposals(timestamps),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jarvis-proposals'] }),
  });

  const handleDismiss = useCallback((ts: number) => {
    dismissMutation.mutate([ts]);
  }, [dismissMutation]);

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['jarvis-handoff-reports'] });
    queryClient.invalidateQueries({ queryKey: ['jarvis-proposals'] });
  }, [queryClient]);

  useWSReconnect(invalidate);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'cortex_handoff_report') {
      queryClient.invalidateQueries({ queryKey: ['jarvis-handoff-reports'] });
    }
    if (msg.type === 'cortex_proposal') {
      queryClient.invalidateQueries({ queryKey: ['jarvis-proposals'] });
    }
  }, [queryClient]));

  const isLoading = reportsLoading || proposalsLoading;
  const reportCount = reports?.length ?? 0;
  const proposalCount = proposals?.length ?? 0;
  const totalCount = reportCount + proposalCount;

  type TimelineEntry =
    | { type: 'handoff'; ts: number; data: HandoffReport }
    | { type: 'proposal'; ts: number; data: EnhancementProposal };

  const timeline: TimelineEntry[] = [];
  if (filter !== 'proposals' && reports) {
    for (const r of reports) timeline.push({ type: 'handoff', ts: r.timestamp, data: r });
  }
  if (filter !== 'handoff' && proposals) {
    for (const p of proposals) timeline.push({ type: 'proposal', ts: p.timestamp, data: p });
  }
  timeline.sort((a, b) => b.ts - a.ts);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-border bg-bg-secondary">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <h2 className="text-sm font-semibold text-text-primary">JARVIS Memory</h2>
            {totalCount > 0 && (
              <span className="text-[11px] text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
                {totalCount} entries
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {(['all', 'handoff', 'proposals'] as FilterMode[]).map((mode) => (
              <button key={mode} onClick={() => setFilter(mode)}
                className={`px-2 py-1 text-[11px] rounded transition-colors ${
                  filter === mode
                    ? 'bg-accent/20 text-accent'
                    : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
                }`}>
                {mode === 'all' ? `All (${totalCount})`
                  : mode === 'handoff' ? `Handoffs (${reportCount})`
                  : `Proposals (${proposalCount})`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {isLoading ? (
          <div className="text-sm text-text-muted text-center py-12">Loading JARVIS memory...</div>
        ) : timeline.length === 0 ? (
          <div className="text-center py-12">
            <Lightbulb className="w-8 h-8 text-text-muted mx-auto mb-2 opacity-40" />
            <p className="text-sm text-text-muted">No JARVIS memory entries yet.</p>
            <p className="text-xs text-text-muted mt-1">
              Handoff reports appear after JARVIS session rotations. Proposals are created when JARVIS identifies feature gaps.
            </p>
          </div>
        ) : (
          timeline.map((entry, i) => (
            <div key={`${entry.type}-${entry.ts}-${i}`}>
              {entry.type === 'handoff'
                ? <HandoffCard report={entry.data as HandoffReport} />
                : <ProposalCard proposal={entry.data as EnhancementProposal} onDismiss={handleDismiss} />}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
