// BlackBoard/ui/src/components/FlowHistoryPage.tsx
// @ai-rules:
// 1. [Pattern]: Uses recharts LineChart with ResponsiveContainer for sparklines.
// 2. [Pattern]: Time range selector drives useFlowHistory hook (React Query 30s polling).
// 3. [Constraint]: No external ErrorBoundary dep — parent wraps with local class component.
// 4. [Gotcha]: Downsampled data has same FlowSnapshot shape — transparent to charts.
/**
 * WIP tab: time-series flow health visualizations.
 */
import { useState } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis, XAxis } from 'recharts';
import { useFlowHistory } from '../hooks/useFlowHistory';
import type { FlowSnapshot } from '../api/types';

const RANGES = [
  { label: '1h', seconds: 3600 },
  { label: '6h', seconds: 21600 },
  { label: '24h', seconds: 86400 },
  { label: '7d', seconds: 604800 },
] as const;

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

interface SparkCardProps {
  title: string;
  data: FlowSnapshot[];
  dataKey: keyof FlowSnapshot;
  color: string;
  unit?: string;
}

function SparkCard({ title, data, dataKey, color, unit = '' }: SparkCardProps) {
  const latest = data.length > 0 ? data[data.length - 1][dataKey] : 0;
  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-primary">{title}</h3>
        <span className="text-lg font-mono" style={{ color }}>
          {typeof latest === 'number' ? latest.toFixed(dataKey.toString().includes('sec') || dataKey.toString().includes('ms') ? 1 : 0) : latest}{unit}
        </span>
      </div>
      <div className="h-16">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <YAxis hide domain={['auto', 'auto']} />
            <XAxis hide dataKey="timestamp" />
            <Tooltip
              labelFormatter={(v) => formatTime(v as number)}
              formatter={(v: number | undefined) => [`${(v ?? 0).toFixed(1)}${unit}`, title]}
              contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function FlowHistoryPage() {
  const [rangeIdx, setRangeIdx] = useState(0);
  const range = RANGES[rangeIdx];
  const { data, isLoading, error } = useFlowHistory(range.seconds);

  if (error) {
    return (
      <div className="p-6 text-text-muted">
        Flow history unavailable. <button className="underline" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-24 bg-bg-secondary animate-pulse rounded-lg" />
        ))}
      </div>
    );
  }

  const snapshots = data ?? [];

  if (snapshots.length === 0) {
    return (
      <div className="p-6 text-text-muted">
        Collecting data... first snapshot in ~60s.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">Flow Health</h2>
        <div className="flex gap-1">
          {RANGES.map((r, i) => (
            <button
              key={r.label}
              onClick={() => setRangeIdx(i)}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                i === rangeIdx
                  ? 'bg-accent text-white'
                  : 'bg-bg-secondary text-text-muted hover:text-text-primary'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SparkCard title="Queue Depth" data={snapshots} dataKey="queue_depth" color="#3b82f6" />
        <SparkCard title="Active Events" data={snapshots} dataKey="active_events" color="#22c55e" />
        <SparkCard title="Deferred Events" data={snapshots} dataKey="deferred_events" color="#f59e0b" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SparkCard title="Waiting Approval" data={snapshots} dataKey="waiting_approval_events" color="#f97316" />
        <SparkCard title="HH Pending" data={snapshots} dataKey="headhunter_pending" color="#ef4444" />
        <SparkCard title="Avg Event Age" data={snapshots} dataKey="avg_event_age_sec" color="#8b5cf6" unit="s" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SparkCard title="Agent Utilization" data={snapshots} dataKey="busy_agents" color="#06b6d4" />
        <SparkCard title="Reconcile Latency" data={snapshots} dataKey="avg_reconcile_ms" color="#ec4899" unit="ms" />
        <SparkCard title="Subscriptions" data={snapshots} dataKey="active_subscriptions" color="#64748b" />
      </div>
    </div>
  );
}
