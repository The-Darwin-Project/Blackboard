// BlackBoard/ui/src/components/ServiceMetricChart.tsx
// @ai-rules:
// 1. [Pattern]: Hover opens a fixed-position enlarged popup. Mouse leave on popup closes it.
// 2. [Constraint]: Popup uses a portal-less approach -- rendered inline with fixed positioning.
// 3. [Pattern]: Same chartData used for both inline card and popup (no re-fetch).
/**
 * Single-service chart component for displaying metrics in a grid layout.
 * Shows CPU, Memory, and Error Rate for one service.
 * Hover opens an enlarged popup view; mouse leave closes it.
 */
import { useMemo, useState, useRef } from 'react';
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

export function ServiceMetricChart({ service, data, events: _events }: ServiceMetricChartProps) {
  const [hovered, setHovered] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

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

  // Compute popup position anchored to card
  const getPopupPos = () => {
    if (!cardRef.current) return { top: 100, left: 100 };
    const rect = cardRef.current.getBoundingClientRect();
    // Position to the left of the card, vertically centered
    const popupW = 420;
    const popupH = 280;
    let left = rect.left - popupW - 12;
    let top = rect.top + (rect.height / 2) - (popupH / 2);
    // If it would go off-screen left, position above instead
    if (left < 8) {
      left = rect.left;
      top = rect.top - popupH - 12;
    }
    // Clamp to viewport
    if (top < 8) top = 8;
    if (top + popupH > window.innerHeight - 8) top = window.innerHeight - popupH - 8;
    return { top, left };
  };

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

  const popupPos = hovered ? getPopupPos() : { top: 0, left: 0 };

  return (
    <>
      {/* Inline card */}
      <div
        ref={cardRef}
        style={{ minWidth: 100 }}
        className="bg-bg-primary rounded-lg p-3 border border-border cursor-pointer transition-colors hover:border-accent/50"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <h3 className="text-xs font-medium text-text-primary mb-1 truncate" title={service}>{service}</h3>
        <ResponsiveContainer width="100%" height={120}>
          <ChartContent chartData={chartData} />
        </ResponsiveContainer>
      </div>

      {/* Enlarged popup on hover */}
      {hovered && (
        <div
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{
            position: 'fixed',
            top: popupPos.top,
            left: popupPos.left,
            width: 420,
            height: 280,
            background: '#0f172a',
            border: '2px solid #3b82f6',
            borderRadius: 12,
            padding: 16,
            zIndex: 1000,
            boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h3 style={{ color: '#e2e8f0', fontSize: 14, fontWeight: 600, margin: 0 }}>{service}</h3>
            <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
              <span style={{ color: '#3b82f6' }}>CPU</span>
              <span style={{ color: '#8b5cf6' }}>Memory</span>
              <span style={{ color: '#ef4444' }}>Error Rate</span>
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ChartContent chartData={chartData} />
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </>
  );
}

export default ServiceMetricChart;
