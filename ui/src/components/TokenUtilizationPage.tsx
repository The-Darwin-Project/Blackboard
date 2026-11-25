// BlackBoard/ui/src/components/TokenUtilizationPage.tsx
// @ai-rules:
// 1. [Pattern]: Mirrors FlowHistoryPage SparkCard inline pattern (not extracted).
// 2. [Pattern]: Combines FlowSnapshot SparkCards (aggregate + Claude/Sidecar runtime deltas) with a fail-open
//    GET /telemetry/llm By Pool & By Caller (+ non-empty teams) breakdown card.
// 3. [Pattern]: Uses useFlowHistory hook with time range selector (same as FlowHistoryPage).
import { useEffect, useState } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis, XAxis } from 'recharts';
import { getLlmTelemetry } from '../api/client';
import { useFlowHistory } from '../hooks/useFlowHistory';
import { formatTokenCount } from '../utils/formatTokens';
import type { FlowSnapshot, LlmTelemetryBreakdown } from '../api/types';

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

function SparkCard({ title, data, dataKey, color, subtitle }: {
  title: string; data: FlowSnapshot[]; dataKey: keyof FlowSnapshot; color: string; subtitle?: string;
}) {
  const values = data.map(s => (s[dataKey] as number | undefined) ?? 0);
  const n = values.length;
  const rangeTotal = values.reduce((a, b) => a + b, 0);
  const rms = n > 0 ? Math.round(Math.sqrt(values.reduce((a, v) => a + v * v, 0) / n)) : 0;
  const isCalls = dataKey === 'token_calls_delta';
  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-sm font-medium text-text-primary">{title}</h3>
          {subtitle && (
            <div className="text-[10px] text-text-muted font-mono">{subtitle}</div>
          )}
        </div>
        <div className="text-right">
          <span className="text-lg font-mono" style={{ color }}>
            {isCalls ? rms : formatTokens(rms)}
          </span>
          <span className="text-[10px] text-text-muted ml-1">rms</span>
          <div className="text-[10px] text-text-muted/70 font-mono">
            {isCalls ? rangeTotal : formatTokens(rangeTotal)} total
          </div>
        </div>
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
  const [breakdown, setBreakdown] = useState<LlmTelemetryBreakdown | null>(null);
  const range = RANGES[rangeIdx];
  const { data, isLoading, error } = useFlowHistory(range.seconds);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const json = await getLlmTelemetry();
        if (!cancelled && json && typeof json === 'object') setBreakdown(json);
      } catch {
        // Fail-open: SparkCards remain visible when /telemetry/llm is unreachable
      }
    })();
    return () => { cancelled = true; };
  }, []);

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
  const totalInput = snapshots.reduce((a, s) => a + (s.token_input_delta ?? 0), 0);
  const totalCached = snapshots.reduce((a, s) => a + (s.token_cached_delta ?? 0), 0);
  const brainInput = snapshots.reduce((a, s) => a + (s.brain_token_input_delta ?? 0), 0);
  const brainCached = snapshots.reduce((a, s) => a + (s.brain_token_cached_delta ?? 0), 0);
  const cacheHitPct = totalInput > 0 ? ((totalCached / totalInput) * 100).toFixed(1) : '0.0';
  const brainHitPct = brainInput > 0 ? ((brainCached / brainInput) * 100).toFixed(1) : '0.0';

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
        <SparkCard
          title="Cached Tokens"
          data={snapshots}
          dataKey="token_cached_delta"
          color="#fbbf24"
          subtitle={`${cacheHitPct}% hit (Brain: ${brainHitPct}%)`}
        />
        <SparkCard title="LLM Calls" data={snapshots} dataKey="token_calls_delta" color="#fb923c" />
        <SparkCard
          title="Claude Tokens"
          data={snapshots}
          dataKey="claude_token_total_delta"
          color="#e879f9"
          subtitle="in-process + sidecar:claude"
        />
        <SparkCard
          title="Sidecar Tokens"
          data={snapshots}
          dataKey="sidecar_token_total_delta"
          color="#38bdf8"
          subtitle="sidecar:agy + sidecar:claude"
        />
      </div>

      {breakdown && (
        <div className="bg-bg-secondary border border-border rounded-lg p-4 space-y-3" data-testid="telemetry-breakdown-card">
          <h3 className="text-sm font-medium text-text-primary">By Pool &amp; By Caller</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            <div>
              <div className="text-text-muted mb-1">Pools (60s)</div>
              {Object.entries(breakdown.pools ?? {}).map(([pool, stats]) => (
                <div key={pool} className="flex justify-between py-0.5 text-text-secondary">
                  <span>{pool}</span>
                  <span>{formatTokens(stats.tokens_used_60s ?? 0)} / {formatTokens(stats.tpm_limit ?? 0)} ({(stats.utilization_pct ?? 0).toFixed(1)}%)</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-text-muted mb-1">Callers (since boot)</div>
              {Object.entries(breakdown.callers ?? {}).map(([caller, stats]) => (
                <div key={caller} className="flex justify-between py-0.5 text-text-secondary">
                  <span>{caller}</span>
                  <span>{formatTokens(stats.total_tokens ?? 0)} ({stats.calls ?? 0})</span>
                </div>
              ))}
            </div>
            {breakdown.teams && Object.keys(breakdown.teams).length > 0 && (
              <div>
                <div className="text-text-muted mb-1">Teams</div>
                {Object.entries(breakdown.teams).map(([team, stats]) => (
                  <div key={team} className="flex justify-between py-0.5 text-text-secondary">
                    <span>{team}</span>
                    <span>{formatTokens(stats.total_tokens ?? 0)} ({stats.calls ?? 0})</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
