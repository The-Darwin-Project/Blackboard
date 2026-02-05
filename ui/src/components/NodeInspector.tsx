// BlackBoard/ui/src/components/NodeInspector.tsx
/**
 * Slide-over drawer for service details and plan actions.
 * Shows metrics, dependencies, recent events, and plan approval buttons.
 */
import { X, Activity, Cpu, HardDrive, AlertTriangle, Clock, GitBranch, CheckCircle, XCircle, Ghost, FileText, Zap } from 'lucide-react';
import { useService, usePlans, useApprovePlan, useRejectPlan, useEvents } from '../hooks';
import type { Plan, ArchitectureEvent } from '../api/types';

// Event type to human-readable label mapping
const EVENT_LABELS: Record<string, string> = {
  service_discovered: 'Discovered',
  high_cpu_detected: 'High CPU',
  high_memory_detected: 'High Memory',
  high_error_rate_detected: 'High Error Rate',
  deployment_detected: 'Deployment',
  anomaly_resolved: 'Resolved',
  architect_analyzing: 'Analyzing',
  plan_created: 'Plan Created',
  plan_approved: 'Plan Approved',
  plan_executed: 'Plan Executed',
  plan_failed: 'Plan Failed',
  sysadmin_executing: 'Executing',
};

interface NodeInspectorProps {
  serviceName: string | null;
  planId?: string | null;
  onClose: () => void;
}

function NodeInspector({ serviceName, planId, onClose }: NodeInspectorProps) {
  const { data: service, isLoading } = useService(serviceName);
  const { data: plans } = usePlans();
  const { data: events } = useEvents(50, serviceName ?? undefined);  // Filter events by service
  const { mutate: approvePlan, isPending: isApproving } = useApprovePlan();
  const { mutate: rejectPlan, isPending: isRejecting } = useRejectPlan();

  // Find the selected plan
  const selectedPlan = planId ? plans?.find((p: Plan) => p.id === planId) : null;

  // If showing a plan, display plan details
  if (planId && selectedPlan) {
    return (
      <>
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />

        {/* Drawer */}
        <div className="fixed right-0 top-0 h-full w-80 bg-bg-secondary border-l border-border z-50 shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Ghost className="w-5 h-5 text-purple-400" />
              <h3 className="font-semibold text-text-primary">Plan Details</h3>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-bg-tertiary transition-colors"
            >
              <X className="w-5 h-5 text-text-muted" />
            </button>
          </div>

          {/* Plan Content */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            {/* Plan ID */}
            <div className="flex items-center gap-2 text-sm">
              <FileText className="w-4 h-4 text-text-muted" />
              <span className="text-text-secondary">Plan ID:</span>
              <span className="text-text-primary font-mono text-xs">{selectedPlan.id}</span>
            </div>

            {/* Action */}
            <div className="flex items-center gap-2 text-sm">
              <Activity className="w-4 h-4 text-text-muted" />
              <span className="text-text-secondary">Action:</span>
              <span className="text-text-primary font-semibold uppercase">{selectedPlan.action}</span>
            </div>

            {/* Target Service */}
            <div className="flex items-center gap-2 text-sm">
              <GitBranch className="w-4 h-4 text-text-muted" />
              <span className="text-text-secondary">Target:</span>
              <span className="text-text-primary">{selectedPlan.service}</span>
            </div>

            {/* Status */}
            <div className="flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-text-muted" />
              <span className="text-text-secondary">Status:</span>
              <span className={`font-semibold ${
                selectedPlan.status === 'pending' ? 'text-yellow-400' :
                selectedPlan.status === 'approved' ? 'text-green-400' :
                selectedPlan.status === 'rejected' ? 'text-red-400' :
                'text-text-primary'
              }`}>
                {selectedPlan.status}
              </span>
            </div>

            {/* Reason */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-text-secondary">Reason</h4>
              <p className="text-sm text-text-primary bg-bg-primary rounded p-3">
                {selectedPlan.reason}
              </p>
            </div>

            {/* Parameters */}
            {Object.keys(selectedPlan.params).length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-text-secondary">Parameters</h4>
                <div className="bg-bg-primary rounded p-3">
                  <pre className="text-xs text-text-primary font-mono whitespace-pre-wrap">
                    {JSON.stringify(selectedPlan.params, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Approve/Reject Buttons */}
            {selectedPlan.status === 'pending' && (
              <div className="flex gap-2 pt-4 border-t border-border">
                <button
                  onClick={() => approvePlan(selectedPlan.id)}
                  disabled={isApproving || isRejecting}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve
                </button>
                <button
                  onClick={() => rejectPlan({ id: selectedPlan.id })}
                  disabled={isApproving || isRejecting}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  Reject
                </button>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  // Otherwise show service details
  if (!serviceName) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-80 bg-bg-secondary border-l border-border z-50 shadow-xl overflow-hidden flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
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

              {/* Metrics */}
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-text-secondary">Metrics</h4>
                <div className="grid grid-cols-1 gap-2">
                  <MetricBar
                    icon={<Cpu className="w-4 h-4" />}
                    label="CPU"
                    value={service.metrics.cpu}
                    color="text-blue-400"
                  />
                  <MetricBar
                    icon={<HardDrive className="w-4 h-4" />}
                    label="Memory"
                    value={service.metrics.memory}
                    color="text-purple-400"
                  />
                  <MetricBar
                    icon={<AlertTriangle className="w-4 h-4" />}
                    label="Error Rate"
                    value={service.metrics.error_rate}
                    color="text-red-400"
                    threshold={5}
                  />
                </div>
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

interface MetricBarProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
  threshold?: number;
}

function MetricBar({ icon, label, value, color, threshold }: MetricBarProps) {
  const isAboveThreshold = threshold !== undefined && value > threshold;
  const barColor = isAboveThreshold ? 'bg-status-critical' : 'bg-accent';

  return (
    <div className="bg-bg-primary rounded-lg p-2">
      <div className="flex items-center justify-between mb-1">
        <div className={`flex items-center gap-2 ${color}`}>
          {icon}
          <span className="text-xs">{label}</span>
        </div>
        <span className={`text-xs font-mono ${isAboveThreshold ? 'text-status-critical' : 'text-text-primary'}`}>
          {value.toFixed(1)}%
        </span>
      </div>
      <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-300`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
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
