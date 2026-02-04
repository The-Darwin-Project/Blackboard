// BlackBoard/ui/src/components/MetricChart.tsx
/**
 * Recharts-based time-series chart for resource metrics.
 * Shows CPU, Memory, Error Rate lines with event markers.
 */
import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Loader2, BarChart3 } from 'lucide-react';
import { useMetrics } from '../hooks';
import type { ArchitectureEvent, MetricSeries } from '../api/types';

// Metric colors
const METRIC_COLORS = {
  cpu: '#3b82f6',      // Blue
  memory: '#8b5cf6',   // Purple
  error_rate: '#ef4444', // Red
};

// Event type colors
const EVENT_COLORS: Record<string, string> = {
  plan_created: '#f59e0b',
  plan_approved: '#22c55e',
  plan_executed: '#10b981',
  plan_failed: '#ef4444',
  service_discovered: '#6366f1',
};

function MetricChart() {
  const { data, isLoading, isError } = useMetrics();

  // Transform data for Recharts
  const chartData = useMemo(() => {
    if (!data?.series?.length) return [];

    // Group data points by timestamp
    const timeMap = new Map<number, Record<string, number>>();

    data.series.forEach((series: MetricSeries) => {
      series.data.forEach((point) => {
        // Round timestamp to nearest second for grouping
        const roundedTime = Math.round(point.timestamp);
        
        if (!timeMap.has(roundedTime)) {
          timeMap.set(roundedTime, { timestamp: roundedTime });
        }
        
        const entry = timeMap.get(roundedTime)!;
        const key = `${series.service}_${series.metric}`;
        entry[key] = point.value;
      });
    });

    // Convert to array and sort by time
    return Array.from(timeMap.values()).sort((a, b) => a.timestamp - b.timestamp);
  }, [data]);

  // Get unique series keys for rendering lines
  const seriesKeys = useMemo(() => {
    if (!data?.series?.length) return [];
    
    return data.series.map((series: MetricSeries) => ({
      key: `${series.service}_${series.metric}`,
      service: series.service,
      metric: series.metric,
      color: METRIC_COLORS[series.metric as keyof typeof METRIC_COLORS] || '#64748b',
    }));
  }, [data]);

  // Get events for reference lines
  const events = useMemo(() => {
    if (!data?.events?.length) return [];
    return data.events.filter((e: ArchitectureEvent) => 
      e.type.startsWith('plan_') || e.type === 'service_discovered'
    );
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

  if (!chartData.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <BarChart3 className="w-12 h-12" />
        <p className="text-sm">No metrics data</p>
        <p className="text-xs">Services will appear when telemetry is received</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200} minWidth={300}>
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(value) => new Date(value * 1000).toLocaleTimeString()}
          stroke="#64748b"
          fontSize={10}
        />
        <YAxis
          stroke="#64748b"
          fontSize={10}
          domain={[0, 100]}
          tickFormatter={(value) => `${value}%`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#1e293b',
            border: '1px solid #334155',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          labelFormatter={(value) => new Date(Number(value) * 1000).toLocaleString()}
          formatter={(value) => [`${Number(value).toFixed(1)}%`, '']}
        />
        <Legend
          wrapperStyle={{ fontSize: '11px' }}
          formatter={(value) => {
            const [service, metric] = value.split('_');
            return `${service} (${metric})`;
          }}
        />

        {/* Metric Lines */}
        {seriesKeys.map(({ key, color }) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: color }}
          />
        ))}

        {/* Event Reference Lines */}
        {events.map((event: ArchitectureEvent, index: number) => (
          <ReferenceLine
            key={`event-${index}`}
            x={Math.round(event.timestamp)}
            stroke={EVENT_COLORS[event.type] || '#64748b'}
            strokeDasharray="4 4"
            strokeWidth={1}
            label={{
              value: event.type.replace('_', ' '),
              position: 'top',
              fill: '#94a3b8',
              fontSize: 9,
            }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export default MetricChart;
