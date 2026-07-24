// BlackBoard/ui/src/components/OperationTimeline.tsx
// @ai-rules:
// 1. [Pattern]: Merges two evidence sources for a service: Darwin conversation events
//    (active + recently closed, from /queue) and ArgoCD sync operations (Service.last_operations,
//    populated by ArgoCDObserver -- see argocd.py). Sorted newest-first, capped at 20 entries.
// 2. [Constraint]: Client-side filter by service -- there is no server-side per-service
//    /queue filter endpoint; active + closed event lists are already small and polled.
// 3. [Gotcha]: last_operations timestamps are ISO strings from the K8s API (startedAt/
//    finishedAt/deployedAt) -- Date.parse handles them directly, no epoch conversion needed.
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, GitCommit, Clock } from 'lucide-react';
import { useActiveEvents, useService } from '../hooks';
import { getClosedEvents } from '../api/client';
import type { ActiveEvent, ArgoCDOperation } from '../api/types';

interface OperationTimelineProps {
  serviceName: string;
}

type TimelineEntry =
  | { kind: 'event'; timestamp: number; event: ActiveEvent }
  | { kind: 'operation'; timestamp: number; operation: ArgoCDOperation };

function toTimestamp(value?: string): number {
  if (!value) return 0;
  const t = Date.parse(value);
  return Number.isNaN(t) ? 0 : t;
}

function OperationTimeline({ serviceName }: OperationTimelineProps) {
  const { data: service } = useService(serviceName);
  const { data: activeEvents } = useActiveEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents', 50],
    queryFn: () => getClosedEvents(50),
    staleTime: 30_000,
  });

  const entries = useMemo<TimelineEntry[]>(() => {
    const events: TimelineEntry[] = [...(activeEvents ?? []), ...(closedEvents ?? [])]
      .filter((e) => e.service === serviceName)
      .map((event) => ({ kind: 'event', timestamp: toTimestamp(event.created), event }));

    const operations: TimelineEntry[] = (service?.last_operations ?? []).map((operation) => ({
      kind: 'operation',
      timestamp: toTimestamp(operation.finishedAt || operation.startedAt || operation.deployedAt),
      operation,
    }));

    return [...events, ...operations].sort((a, b) => b.timestamp - a.timestamp).slice(0, 20);
  }, [activeEvents, closedEvents, service, serviceName]);

  if (!entries.length) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-text-muted gap-2">
        <Clock className="w-8 h-8" />
        <p className="text-sm">No recent activity</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {entries.map((entry) =>
        entry.kind === 'event' ? (
          <EventEntry key={`event-${entry.event.id}`} event={entry.event} />
        ) : (
          <OperationEntry key={`op-${entry.operation.type}-${entry.timestamp}`} operation={entry.operation} />
        ),
      )}
    </div>
  );
}

function EventEntry({ event }: { event: ActiveEvent }) {
  const isCritical = event.evidence?.severity === 'critical';
  const isWarning = event.evidence?.severity === 'warning';
  return (
    <div className="bg-bg-primary rounded-lg p-2.5 border border-border flex items-start gap-2">
      <AlertCircle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
        isCritical ? 'text-status-critical' : isWarning ? 'text-status-warning' : 'text-accent'
      }`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-text-primary truncate" title={event.reason}>
            {event.reason}
          </span>
          <span className="text-[10px] text-text-muted flex-shrink-0">
            {new Date(event.created).toLocaleString()}
          </span>
        </div>
        <p className="text-[11px] text-text-secondary mt-0.5">{event.source} &middot; {event.status}</p>
      </div>
    </div>
  );
}

function OperationEntry({ operation }: { operation: ArgoCDOperation }) {
  const isCurrent = operation.type === 'current';
  const phase = operation.phase || 'Synced';
  const isFailed = phase === 'Failed' || phase === 'Error';
  const isSuccess = phase === 'Succeeded';
  const timestamp = operation.finishedAt || operation.startedAt || operation.deployedAt;

  return (
    <div className="bg-bg-primary rounded-lg p-2.5 border border-border flex items-start gap-2">
      {isFailed ? (
        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-status-critical" />
      ) : (
        <CheckCircle2 className={`w-4 h-4 mt-0.5 flex-shrink-0 ${isSuccess ? 'text-status-healthy' : 'text-text-muted'}`} />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-text-primary">
            {isCurrent ? `Sync: ${phase}` : 'Deployed'}
          </span>
          <span className="text-[10px] text-text-muted flex-shrink-0">
            {timestamp ? new Date(timestamp).toLocaleString() : 'unknown time'}
          </span>
        </div>
        {operation.revision && (
          <p className="text-[11px] text-text-secondary mt-0.5 font-mono flex items-center gap-1">
            <GitCommit className="w-3 h-3" /> {operation.revision.slice(0, 8)}
          </p>
        )}
      </div>
    </div>
  );
}

export default OperationTimeline;
