// BlackBoard/ui/src/components/ServiceMetricChart.tsx
// @ai-rules:
// 1. [Pattern]: Inline card only -- no hover popup. Click delegates to parent via onClick prop.
// 2. [Pattern]: enlarged prop renders a taller chart with legend header for highlighted services.
// 3. [Pattern]: Same chartData used for both inline card and enlarged (no re-fetch).
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
  onClick?: () => void;
  enlarged?: boolean;
}

const CHART_LINES = [
  { dataKey: 'cpu', stroke: '#3b82f6', name: 'CPU %' },
  { dataKey: 'memory', stroke: '#8b5cf6', name: 'Memory %' },
  { dataKey: 'error_rate', stroke: '#ef4444', name: 'Error Rate' },
] as const;

function ChartContent({ chartData }: { chartData: Record<string, number>[] }) {
  return (
    <LineChart data={chartData}>
      <XAxis dataKey="timestamp" hide />
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
      {CHART_LINES.map((line) => (
        <Line
          key={line.dataKey}
          type="stepAfter"
          dataKey={line.dataKey}
          stroke={line.stroke}
          strokeWidth={2}
          dot={false}
          name={line.name}
          connectNulls
        />
      ))}
    </LineChart>
  );
}

export function ServiceMetricChart({ service, data, events: _events, onClick, enlarged }: ServiceMetricChartProps) {
  const serviceData = useMemo(() => data.filter(s => s.service === service), [data, service]);

  const chartData = useMemo(() => {
    if (!serviceData.length) return [];
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

  const chartHeight = enlarged ? 200 : 140;

  if (!chartData.length) {
    return (
      <div className="bg-bg-primary rounded-lg p-3 border border-border">
        <h3 className={`font-medium text-text-primary mb-2 truncate ${enlarged ? 'text-sm' : 'text-xs'}`} title={service}>{service}</h3>
        <div style={{ height: chartHeight }} className="flex items-center justify-center text-text-muted text-xs">
          No data
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-bg-primary rounded-lg p-3 border transition-colors ${enlarged ? 'border-accent/40' : 'border-border cursor-pointer hover:border-accent/50'}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-1">
        <h3 className={`font-medium text-text-primary truncate ${enlarged ? 'text-sm' : 'text-xs'}`} title={service}>{service}</h3>
        {enlarged && (
          <div className="flex gap-3 text-[11px] flex-shrink-0">
            <span style={{ color: '#3b82f6' }}>CPU</span>
            <span style={{ color: '#8b5cf6' }}>Memory</span>
            <span style={{ color: '#ef4444' }}>Error Rate</span>
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <ChartContent chartData={chartData} />
      </ResponsiveContainer>
    </div>
  );
}

export default ServiceMetricChart;
