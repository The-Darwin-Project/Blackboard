// BlackBoard/ui/src/components/NodeInspector.tsx
// @ai-rules:
// 1. [Pattern]: Status section (Health/Sync/Namespace/Last Operation) replaces the old
//    CPU/Memory/Error-Rate MetricBar section -- ArgoCD is the sole health source now.
/**
 * Slide-over drawer for service details.
 * Shows ArgoCD health/sync status, dependencies, and recent events.
 */
import { X, Activity, HeartPulse, RefreshCw, Layers, Clock, GitBranch, Zap } from 'lucide-react';
import { useService, useEvents } from '../hooks';
import type { ArchitectureEvent, ArgoCDOperation } from '../api/types';

// Event type to human-readable label mapping
const EVENT_LABELS: Record<string, string> = {
  service_discovered: 'Discovered',
  high_cpu_detected: 'High CPU',
  high_memory_detected: 'High Memory',
  high_error_rate_detected: 'High Error Rate',
  deployment_detected: 'Deployment',
  anomaly_resolved: 'Resolved',
  aligner_observation: 'Observation',
  architect_analyzing: 'Analyzing',
  sysadmin_executing: 'Executing',
};

interface NodeInspectorProps {
  serviceName: string | null;
  onClose: () => void;
  inline?: boolean;
}

function NodeInspector({ serviceName, onClose, inline }: NodeInspectorProps) {
  const { data: service, isLoading } = useService(serviceName);
  const { data: events } = useEvents(50, serviceName ?? undefined);

  if (!serviceName) return null;

  const wrapperClass = inline
    ? 'h-full flex flex-col bg-bg-secondary'
    : 'fixed right-0 top-0 h-full w-80 bg-bg-secondary border-l border-border z-50 shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right duration-200';

  return (
    <>
      {!inline && <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />}

      <div className={wrapperClass}>
        {/* Header */}
        <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent" />
            <h3 className="font-semibold text-text-primary">{serviceName}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-bg-tertiary transition-colors"
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {isLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-bg-tertiary rounded w-3/4" />
              <div className="h-24 bg-bg-tertiary rounded" />
              <div className="h-4 bg-bg-tertiary rounded w-1/2" />
              <div className="h-16 bg-bg-tertiary rounded" />
            </div>
          ) : service ? (
            <>
              {/* Version */}
              <div className="flex items-center gap-2 text-sm">
                <GitBranch className="w-4 h-4 text-text-muted" />
                <span className="text-text-secondary">Version:</span>
                <span className="text-text-primary font-mono">{service.version}</span>
              </div>

              {/* Last Seen */}
              <div className="flex items-center gap-2 text-sm">
                <Clock className="w-4 h-4 text-text-muted" />
                <span className="text-text-secondary">Last seen:</span>
                <span className="text-text-primary">
                  {new Date(service.last_seen * 1000).toLocaleTimeString()}
                </span>
              </div>

              {/* Status */}
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-text-secondary">Status</h4>
                <div className="grid grid-cols-1 gap-2">
                  <StatusRow
                    icon={<HeartPulse className="w-4 h-4" />}
                    label="Health"
                    value={service.health_status || 'Unknown'}
                    tone={healthTone(service.health_status)}
                  />
                  <StatusRow
                    icon={<RefreshCw className="w-4 h-4" />}
                    label="Sync"
                    value={service.sync_status || 'Unknown'}
                    tone={syncTone(service.sync_status)}
                  />
                  {service.namespace && (
                    <StatusRow
                      icon={<Layers className="w-4 h-4" />}
                      label="Namespace"
                      value={service.namespace}
                    />
                  )}
                </div>
                {lastOperationSummary(service.last_operations) && (
                  <p className="text-xs text-text-muted px-2">
                    {lastOperationSummary(service.last_operations)}
                  </p>
                )}
              </div>

              {/* Dependencies */}
              {service.dependencies.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-text-secondary">Dependencies</h4>
                  <div className="flex flex-wrap gap-2">
                    {service.dependencies.map((dep) => (
                      <span
                        key={dep}
                        className="px-2 py-1 bg-bg-tertiary rounded text-xs text-text-primary font-mono"
                      >
                        {dep}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Events */}
              {events && events.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-text-secondary flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    Recent Events
                  </h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {events.slice(0, 10).map((event) => (
                      <EventItem key={`${event.type}-${event.timestamp}`} event={event} />
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-text-muted py-8">
              <p>Service not found</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

type StatusTone = 'healthy' | 'warning' | 'critical' | 'neutral';

const TONE_COLORS: Record<StatusTone, string> = {
  healthy: 'text-status-healthy',
  warning: 'text-status-warning',
  critical: 'text-status-critical',
  neutral: 'text-text-primary',
};

function healthTone(healthStatus?: string | null): StatusTone {
  if (healthStatus === 'Healthy') return 'healthy';
  if (healthStatus === 'Progressing') return 'warning';
  if (healthStatus === 'Degraded') return 'critical';
  return 'neutral';
}

function syncTone(syncStatus?: string | null): StatusTone {
  if (syncStatus === 'Synced') return 'healthy';
  if (syncStatus === 'OutOfSync') return 'warning';
  return 'neutral';
}

function lastOperationSummary(operations?: ArgoCDOperation[] | null): string | null {
  const current = operations?.find((op) => op.type === 'current');
  if (!current) return null;
  const when = current.finishedAt || current.startedAt;
  const whenText = when ? new Date(when).toLocaleString() : 'unknown time';
  return `Last sync: ${current.phase || 'unknown'} at ${whenText}`;
}

interface StatusRowProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: StatusTone;
}

function StatusRow({ icon, label, value, tone = 'neutral' }: StatusRowProps) {
  return (
    <div className="bg-bg-primary rounded-lg p-2 flex items-center justify-between">
      <div className="flex items-center gap-2 text-text-muted">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <span className={`text-xs font-mono ${TONE_COLORS[tone]}`}>{value}</span>
    </div>
  );
}

interface EventItemProps {
  event: ArchitectureEvent;
}

function EventItem({ event }: EventItemProps) {
  const label = EVENT_LABELS[event.type] || event.type;
  const time = new Date(event.timestamp * 1000).toLocaleTimeString();
  const isCritical = event.type.includes('failed') || event.type.includes('high_error');
  const isWarning = event.type.includes('high_cpu') || event.type.includes('high_memory');
  const isSuccess = event.type.includes('resolved') || event.type.includes('executed');

  return (
    <div className="bg-bg-primary rounded p-2 text-xs">
      <div className="flex items-center justify-between">
        <span className={`font-medium ${
          isCritical ? 'text-status-critical' :
          isWarning ? 'text-status-warning' :
          isSuccess ? 'text-status-healthy' :
          'text-text-primary'
        }`}>
          {label}
        </span>
        <span className="text-text-muted">{time}</span>
      </div>
      {event.narrative && (
        <p className="text-text-secondary mt-1 line-clamp-2">{event.narrative}</p>
      )}
    </div>
  );
}

export default NodeInspector;
