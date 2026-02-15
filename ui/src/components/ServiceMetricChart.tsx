// BlackBoard/ui/src/components/ServiceMetricChart.tsx
/**
 * Single-service chart component for displaying metrics in a grid layout.
 * Shows CPU, Memory, and Error Rate for one service.
 */
import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import type { MetricSeries, ArchitectureEvent } from '../api/types';

interface ServiceMetricChartProps {
  service: string;
  data: MetricSeries[];
  events?: ArchitectureEvent[];
}

export function ServiceMetricChart({ service, data, events: _events }: ServiceMetricChartProps) {
  // Filter data for this service
  const serviceData = useMemo(() => {
    return data.filter(s => s.service === service);
  }, [data, service]);

  // Transform to chart format
  const chartData = useMemo(() => {
    if (!serviceData.length) return [];
    
    // Group by timestamp across all metrics
    const timestampMap = new Map<number, Record<string, number>>();
    
    serviceData.forEach(series => {
      series.data?.forEach(point => {
        const roundedTime = Math.round(point.timestamp);
        const existing = timestampMap.get(roundedTime) || { timestamp: roundedTime };
        existing[series.metric] = point.value;
        timestampMap.set(roundedTime, existing);
      });
    });
    
    return Array.from(timestampMap.values()).sort((a, b) => a.timestamp - b.timestamp);
  }, [serviceData]);

  if (!chartData.length) {
    return (
      <div style={{ minWidth: 100 }} className="bg-bg-primary rounded-lg p-3 border border-border">
        <h3 className="text-xs font-medium text-text-primary mb-2 truncate" title={service}>{service}</h3>
        <div className="h-[100px] flex items-center justify-center text-text-muted text-xs">
          No data
        </div>
      </div>
    );
  }

  return (
    <div style={{ minWidth: 100 }} className="bg-bg-primary rounded-lg p-3 border border-border">
      <h3 className="text-xs font-medium text-text-primary mb-1 truncate" title={service}>{service}</h3>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={chartData}>
          <XAxis 
            dataKey="timestamp" 
            hide 
          />
          <YAxis hide domain={[0, 'auto']} />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#1e293b', 
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelFormatter={(value) => new Date(Number(value) * 1000).toLocaleTimeString()}
            formatter={(value) => [`${Number(value).toFixed(1)}%`, '']}
          />
          <Line 
            type="stepAfter" 
            dataKey="cpu" 
            stroke="#3b82f6" 
            strokeWidth={2}
            dot={false}
            name="CPU %"
            connectNulls
          />
          <Line 
            type="stepAfter" 
            dataKey="memory" 
            stroke="#8b5cf6" 
            strokeWidth={2}
            dot={false}
            name="Memory %"
            connectNulls
          />
          <Line 
            type="stepAfter" 
            dataKey="error_rate" 
            stroke="#ef4444" 
            strokeWidth={2}
            dot={false}
            name="Error Rate"
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default ServiceMetricChart;
