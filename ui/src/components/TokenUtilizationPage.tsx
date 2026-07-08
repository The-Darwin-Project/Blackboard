// BlackBoard/ui/src/components/TokenUtilizationPage.tsx
// @ai-rules:
// 1. [Pattern]: Mirrors FlowHistoryPage SparkCard inline pattern (not extracted).
// 2. [Constraint]: v1 scope — aggregate-only SparkCards from FlowSnapshot delta fields.
// 3. [Pattern]: Uses useFlowHistory hook with time range selector (same as FlowHistoryPage).
import { useState } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis, XAxis } from 'recharts';
import { useFlowHistory } from '../hooks/useFlowHistory';
import { formatTokenCount } from '../utils/formatTokens';
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

const formatTokens = formatTokenCount;

function SparkCard({ title, data, dataKey, color }: {
  title: string; data: FlowSnapshot[]; dataKey: keyof FlowSnapshot; color: string;
}) {
  const latest = data.length > 0 ? (data[data.length - 1][dataKey] as number) : 0;
  const isCalls = dataKey === 'token_calls_delta';
  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-primary">{title}</h3>
        <span className="text-lg font-mono" style={{ color }}>
          {isCalls ? latest : formatTokens(latest)}
        </span>
      </div>
      <div className="h-16">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <YAxis hide domain={['auto', 'auto']} />
            <XAxis hide dataKey="timestamp" />
            <Tooltip
              labelFormatter={(v) => formatTime(v as number)}
              formatter={(v: number | undefined) => [
                isCalls ? String(v ?? 0) : formatTokens(v ?? 0),
                title,
              ]}
              contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, fontSize: 12 }}
            />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function TokenUtilizationPage() {
  const [rangeIdx, setRangeIdx] = useState(0);
  const range = RANGES[rangeIdx];
  const { data, isLoading, error } = useFlowHistory(range.seconds);

  if (error) {
    return (
      <div className="p-6 text-text-muted">
        Token data unavailable. <button className="underline" onClick={() => window.location.reload()}>Retry</button>
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
    return <div className="p-6 text-text-muted">Collecting data... first snapshot in ~60s.</div>;
  }

  const cumTotal = snapshots.length > 0
    ? (snapshots[snapshots.length - 1].token_total_cumulative ?? 0) : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Token Utilization</h2>
          <p className="text-sm text-text-muted mt-0.5">
            Cumulative since boot: <span className="font-mono text-text-secondary">{formatTokens(cumTotal)}</span>
          </p>
        </div>
        <div className="flex gap-1 bg-bg-secondary border border-border rounded-lg p-1">
          {RANGES.map((r, i) => (
            <button key={r.label} onClick={() => setRangeIdx(i)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                i === rangeIdx ? 'bg-accent text-white' : 'text-text-muted hover:bg-bg-tertiary'
              }`}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SparkCard title="Total Tokens" data={snapshots} dataKey="token_total_delta" color="#60a5fa" />
        <SparkCard title="Input Tokens" data={snapshots} dataKey="token_input_delta" color="#34d399" />
        <SparkCard title="Output Tokens" data={snapshots} dataKey="token_output_delta" color="#f472b6" />
        <SparkCard title="Thinking Tokens" data={snapshots} dataKey="token_thinking_delta" color="#a78bfa" />
        <SparkCard title="Cached Tokens" data={snapshots} dataKey="token_cached_delta" color="#fbbf24" />
        <SparkCard title="LLM Calls" data={snapshots} dataKey="token_calls_delta" color="#fb923c" />
      </div>
    </div>
  );
}
