// BlackBoard/ui/src/components/MetricChart.tsx
/**
 * Grid container for service metric charts.
 * Displays separate charts per service in a 2-column grid layout.
 */
import { useMemo } from 'react';
import { Loader2, BarChart3 } from 'lucide-react';
import { useMetrics } from '../hooks';
import { ServiceMetricChart } from './ServiceMetricChart';

function MetricChart() {
  const { data, isLoading, isError } = useMetrics();

  // Extract unique services from the data
  const services = useMemo(() => {
    if (!data?.series) return [];
    return [...new Set(data.series.map(s => s.service))];
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
      
      {/* Service charts grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
