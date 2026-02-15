// BlackBoard/ui/src/components/MetricChart.tsx
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
}

function MetricChart({ collapsed }: MetricChartProps) {
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
      
      {/* Service charts grid -- auto-fill with min 100px cards, adapts to panel width */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 8 }}>
        {services.map(service => (
          <ServiceMetricChart
            key={service}
            service={service}
            data={data?.series ?? []}
            events={data?.events}
          />
        ))}
      </div>
    </div>
  );
}

export default MetricChart;
