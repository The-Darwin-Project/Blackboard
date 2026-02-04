// BlackBoard/ui/src/components/NodeInspector.tsx
/**
 * Slide-over drawer for service details.
 * Shows metrics, dependencies, and other service info.
 */
import { X, Activity, Cpu, HardDrive, AlertTriangle, Clock, GitBranch } from 'lucide-react';
import { useService } from '../hooks';

interface NodeInspectorProps {
  serviceName: string | null;
  onClose: () => void;
}

function NodeInspector({ serviceName, onClose }: NodeInspectorProps) {
  const { data: service, isLoading } = useService(serviceName);

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

export default NodeInspector;
