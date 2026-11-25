// BlackBoard/ui/src/components/TpmUsagePanel.tsx
// @ai-rules:
// 1. [Pattern]: QuotaTracker control-loop panel for the WIP tab (PV=tpm_used, SP=tpm_limit, utilization %, throttles).
// 2. [Constraint]: Tolerate optional fields (undefined -> 0) for pre-rollout FlowSnapshot records in Redis.
import { LineChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatTime, formatTokenCount } from '../utils/formatTokens';
import type { FlowSnapshot } from '../api/types';

interface TpmUsagePanelProps {
  snapshots: FlowSnapshot[];
}

export default function TpmUsagePanel({ snapshots }: TpmUsagePanelProps) {
  const latest = snapshots[snapshots.length - 1];
  const latestUsed = latest?.tpm_used ?? 0;
  const latestLimit = [...snapshots].reverse().find((s) => (s.tpm_limit ?? 0) > 0)?.tpm_limit ?? 0;
  const reserveLimit = Math.round(latestLimit * 0.85);
  const rawPeak = latest?.peak_pool_utilization_pct;
  const latestPct = (rawPeak != null && rawPeak > 0) ? rawPeak : (latest?.tpm_utilization_pct ?? 0);
  const latestThrottles = latest?.quota_throttle_delta ?? 0;
  const totalThrottles = snapshots.reduce((sum, s) => sum + (s.quota_throttle_delta ?? 0), 0);
  const hasEnmaas = snapshots.some((s) => (s.enmaas_tpm_used ?? 0) > 0);
  const chartData = snapshots.map((s) => ({
    timestamp: s.timestamp,
    tpm_used: s.tpm_used ?? 0,
    gemini_tpm_used: s.gemini_tpm_used ?? 0,
    claude_tpm_used: s.claude_tpm_used ?? 0,
    enmaas_tpm_used: s.enmaas_tpm_used ?? 0,
    tpm_utilization_pct: (s.peak_pool_utilization_pct != null && s.peak_pool_utilization_pct > 0)
      ? s.peak_pool_utilization_pct
      : (s.tpm_utilization_pct ?? 0),
  }));
  const peakUsed = chartData.reduce((max, d) => Math.max(max, d.tpm_used), 0);
  const peakPct = chartData.reduce((max, d) => Math.max(max, d.tpm_utilization_pct), 0);
  const yMax = Math.max(peakUsed, latestLimit, 1);
  const utilColor = latestPct >= 100 ? '#ef4444' : latestPct >= 80 ? '#f59e0b' : '#22c55e';
  const tipStyle = { background: '#1e293b', border: 'none', borderRadius: 8, fontSize: 12 };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="tpm-usage-panel">
      <div className="bg-bg-secondary border border-border rounded-lg p-4 md:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-text-primary">Global TPM Usage</h3>
          <div className="text-sm font-mono">
            <span className="text-lg text-sky-400">{formatTokenCount(latestUsed)}</span>
            {latestLimit > 0 && (
              <span className="text-text-muted ml-1">/ {formatTokenCount(latestLimit)} limit</span>
            )}
          </div>
        </div>
        <div className="h-28">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <YAxis domain={[0, yMax]} allowDecimals={false} tickFormatter={formatTokenCount} width={44} tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <XAxis dataKey="timestamp" tickFormatter={formatTime} minTickGap={30} tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip labelFormatter={(v) => formatTime(v as number)} formatter={(v: number | undefined, name?: string) => [formatTokenCount(v ?? 0), name || 'TPM Used']} contentStyle={tipStyle} />
              {latestLimit > 0 && <ReferenceLine y={latestLimit} stroke="#f59e0b" strokeDasharray="4 4" />}
              {latestLimit > 0 && <ReferenceLine y={reserveLimit} stroke="#94a3b8" strokeDasharray="2 2" label="85% reserve" />}
              <Line type="monotone" dataKey="tpm_used" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="gemini_tpm_used" stroke="#34d399" strokeWidth={1.2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="claude_tpm_used" stroke="#e879f9" strokeWidth={1.2} dot={false} isAnimationActive={false} />
              {hasEnmaas && <Line type="monotone" dataKey="enmaas_tpm_used" stroke="#fbbf24" strokeWidth={1.2} dot={false} isAnimationActive={false} />}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-bg-secondary border border-border rounded-lg p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-text-primary">TPM Utilization</h3>
          <span className="text-lg font-mono" style={{ color: utilColor }}>{latestPct.toFixed(1)}%</span>
        </div>
        <div className="h-16">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <YAxis hide domain={[0, Math.max(100, peakPct)]} />
              <XAxis hide dataKey="timestamp" />
              <Tooltip labelFormatter={(v) => formatTime(v as number)} formatter={(v: number | undefined) => [`${(v ?? 0).toFixed(1)}%`, 'Utilization']} contentStyle={tipStyle} />
              <Line type="monotone" dataKey="tpm_utilization_pct" stroke={utilColor} strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-between text-xs text-text-muted mt-2 font-mono">
          <span>Throttles (range): <strong className={totalThrottles > 0 ? 'text-red-400' : 'text-text-secondary'}>{totalThrottles}</strong></span>
          <span>Latest: {latestThrottles}</span>
        </div>
      </div>
    </div>
  );
}
