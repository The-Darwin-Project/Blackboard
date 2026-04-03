// BlackBoard/ui/src/components/MetricChart.tsx
// @ai-rules:
// 1. [Pattern]: Grid of ServiceMetricChart cards, one per monitored service. Excludes Brain self-monitoring.
// 2. [Pattern]: highlightService prop promotes a filtered service to enlarged view at top (Topology integration).
// 3. [Constraint]: Data from useMetrics hook. No direct API calls.
/**
 * Grid container for service metric charts.
 * Displays separate charts per service in a responsive 1-4 column grid.
 */
import { useMemo } from 'react';
import { Loader2, BarChart3 } from 'lucide-react';
import { useMetrics } from '../hooks';
import { ServiceMetricChart } from './ServiceMetricChart';

interface MetricChartProps {
  collapsed?: boolean;
  highlightServices?: string[];
  onServiceClick?: (service: string) => void;
}

function MetricChart({ collapsed, highlightServices = [], onServiceClick }: MetricChartProps) {
  const { data, isLoading, isError } = useMetrics();

  if (collapsed) return null;

  // Extract unique services from the data, excluding Brain self-monitoring
  const EXCLUDED_SERVICES = ['darwin-brain', 'darwin-blackboard-brain'];
  const services = useMemo(() => {
    if (!data?.series) return [];
    return [...new Set(data.series.map(s => s.service))]
      .filter(s => !EXCLUDED_SERVICES.includes(s));
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <BarChart3 className="w-12 h-12" />
        <p className="text-sm">Unable to load metrics</p>
        <p className="text-xs">Check API connection</p>
      </div>
    );
  }

  if (!services.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <BarChart3 className="w-12 h-12" />
        <p className="text-sm">No metrics data</p>
        <p className="text-xs">Services will appear when telemetry is received</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex items-center justify-end gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-blue-500 rounded" />
          <span className="text-text-secondary">CPU</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-purple-500 rounded" />
          <span className="text-text-secondary">Memory</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-red-500 rounded" />
          <span className="text-text-secondary">Error Rate</span>
        </div>
      </div>
      
      {/* Highlighted services enlarged at top (up to 3 from graph selection) */}
      {highlightServices.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${Math.min(highlightServices.filter(s => services.includes(s)).length, 3)}, 1fr)`,
          gap: 12,
          marginBottom: 16,
        }}>
          {highlightServices.filter(s => services.includes(s)).map(svc => (
            <ServiceMetricChart
              key={svc}
              service={svc}
              data={data?.series ?? []}
              events={data?.events}
              enlarged
            />
          ))}
        </div>
      )}

      {/* Service charts grid -- auto-fill with min 200px cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
        {services.filter(s => !highlightServices.includes(s)).map(service => (
          <ServiceMetricChart
            key={service}
            service={service}
            data={data?.series ?? []}
            events={data?.events}
            onClick={() => onServiceClick?.(service)}
          />
        ))}
      </div>
    </div>
  );
}

export default MetricChart;
