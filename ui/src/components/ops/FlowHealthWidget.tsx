// BlackBoard/ui/src/components/ops/FlowHealthWidget.tsx
// @ai-rules:
// 1. [Pattern]: Pure presentational widget. Data from useFlowMetrics() hook (10s poll).
// 2. [Pattern]: WIP gauge is primary metric; deferred shown as breakdown.
// 3. [Constraint]: No direct API calls -- delegates to useFlowMetrics() hook.
import { Layers, Users, Inbox, Radar } from 'lucide-react';
import { useFlowMetrics } from '../../hooks/useFlowMetrics';

function wipColor(pct: number): string {
  if (pct < 60) return 'text-status-healthy';
  if (pct < 85) return 'text-yellow-400';
  return 'text-status-critical';
}

function queueColor(depth: number): string {
  if (depth === 0) return 'text-status-healthy';
  if (depth <= 3) return 'text-yellow-400';
  return 'text-status-critical';
}

export default function FlowHealthWidget() {
  const { data, isError, isLoading } = useFlowMetrics();

  if (isLoading && !data) {
    return (
      <div className="p-2 text-[11px] text-text-muted">Loading flow metrics...</div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-2 text-[11px] text-text-muted italic">
        Flow data unavailable
      </div>
    );
  }

  const totalAgents = data.busy_agents + data.idle_agents;
  const roles = Object.entries(data.agents_by_role);
  const wipPct = data.wip_utilization_pct ?? 0;
  const activeProcessing = data.active_events - (data.deferred_events ?? 0);

  return (
    <div className="p-2 space-y-1.5">
      {/* WIP gauge + queue */}
      <div className="flex items-center gap-3 text-[11px]">
        <div className="flex items-center gap-1" title={`WIP: ${data.wip_used}/${data.wip_cap} (${wipPct}%)`}>
          <Layers className={`w-3 h-3 ${wipColor(wipPct)}`} />
          <span className={`font-semibold ${wipColor(wipPct)}`}>
            {data.wip_used}/{data.wip_cap}
          </span>
          <span className="text-text-muted">WIP</span>
          <span className={`text-[10px] ${wipColor(wipPct)}`}>({wipPct}%)</span>
        </div>
        <div className="flex items-center gap-1" title="Queue depth (NEW events)">
          <Inbox className={`w-3 h-3 ${queueColor(data.queue_depth)}`} />
          <span className={`font-semibold ${queueColor(data.queue_depth)}`}>{data.queue_depth}</span>
          <span className="text-text-muted">queue</span>
        </div>
        <div className="flex items-center gap-1" title="Agent utilization">
          <Users className="w-3 h-3 text-text-secondary" />
          <span className="font-semibold text-text-primary">{data.busy_agents}/{totalAgents}</span>
          <span className="text-text-muted">busy</span>
        </div>
        {(data.active_subscriptions ?? 0) > 0 && (
          <div className="flex items-center gap-1" title="Active state subscriptions">
            <Radar className="w-3 h-3 text-cyan-400" />
            <span className="font-semibold text-cyan-400">{data.active_subscriptions}</span>
            <span className="text-text-muted">watching</span>
          </div>
        )}
      </div>

      {/* WIP breakdown: processing vs deferred */}
      <div className="flex items-center gap-3 text-[10px] text-text-muted">
        <span>{activeProcessing} processing</span>
        {(data.deferred_events ?? 0) > 0 && (
          <span>{data.deferred_events} deferred</span>
        )}
        {(data.waiting_approval_events ?? 0) > 0 && (
          <span>{data.waiting_approval_events} awaiting approval</span>
        )}
        {(data.headhunter_pending ?? 0) > 0 && (
          <span>{data.headhunter_pending} HH pending</span>
        )}
      </div>

      {/* Per-role breakdown */}
      {roles.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-text-muted">
          {roles.map(([role, counts]) => (
            <span key={role} className="flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${counts.busy > 0 ? 'bg-yellow-400' : 'bg-status-healthy'}`} />
              {role}
              <span className="text-text-secondary">
                {counts.busy > 0 ? `${counts.busy} busy` : 'idle'}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
