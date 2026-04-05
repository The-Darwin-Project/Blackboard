// BlackBoard/ui/src/components/ops/FlowHealthWidget.tsx
import { Layers, Users, Inbox } from 'lucide-react';
import { useFlowMetrics } from '../../hooks/useFlowMetrics';

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

  return (
    <div className="p-2 space-y-1.5">
      {/* Top stats row */}
      <div className="flex items-center gap-3 text-[11px]">
        <div className="flex items-center gap-1" title="Queue depth">
          <Inbox className={`w-3 h-3 ${queueColor(data.queue_depth)}`} />
          <span className={`font-semibold ${queueColor(data.queue_depth)}`}>{data.queue_depth}</span>
          <span className="text-text-muted">queue</span>
        </div>
        <div className="flex items-center gap-1" title="Active events">
          <Layers className="w-3 h-3 text-text-secondary" />
          <span className="font-semibold text-text-primary">{data.active_events}</span>
          <span className="text-text-muted">active</span>
        </div>
        <div className="flex items-center gap-1" title="Agent utilization">
          <Users className="w-3 h-3 text-text-secondary" />
          <span className="font-semibold text-text-primary">{data.busy_agents}/{totalAgents}</span>
          <span className="text-text-muted">busy</span>
        </div>
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
