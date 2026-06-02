// BlackBoard/ui/src/components/ObservationCard.tsx
// @ai-rules:
// 1. [Pattern]: Self-contained card with recharts sparkline + stats.
// 2. [Constraint]: Uses snake_case props matching API types.
/**
 * Single observation series card with sparkline and temporal stats.
 */
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import type { ObservationSeries } from '../api/types';

const TREND_CONFIG = {
  rising: { icon: TrendingUp, color: '#f59e0b', label: 'Rising' },
  falling: { icon: TrendingDown, color: '#22c55e', label: 'Falling' },
  stable: { icon: Minus, color: '#64748b', label: 'Stable' },
} as const;

export default function ObservationCard({ series }: { series: ObservationSeries }) {
  const { icon: TrendIcon, color: trendColor, label: trendLabel } = TREND_CONFIG[series.trend];
  const chartData = series.points.map(p => ({
    value: p.value,
    ts: p.timestamp.replace('T', ' ').replace('Z', ''),
  }));

  return (
    <div className="bg-bg-secondary border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-primary truncate">{series.name}</h3>
        <div className="flex items-center gap-1 text-xs" style={{ color: trendColor }}>
          <TrendIcon size={14} />
          <span>{trendLabel}</span>
        </div>
      </div>

      <div className="h-16 mb-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <YAxis domain={['auto', 'auto']} hide />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 12 }}
              labelStyle={{ color: '#94a3b8' }}
              formatter={(val: number | undefined) => [`${val ?? 0} ${series.unit}`, series.name]}
              labelFormatter={(label) => String(label)}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={trendColor}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, fill: trendColor }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs text-text-secondary">
        <div>
          <span className="text-text-muted">Latest</span>
          <div className="text-text-primary font-mono">
            {series.latest_value} {series.unit}
          </div>
        </div>
        <div>
          <span className="text-text-muted">Range</span>
          <div className="text-text-primary font-mono">
            {series.min}–{series.max}
          </div>
        </div>
        <div>
          <span className="text-text-muted">Points</span>
          <div className="text-text-primary font-mono">
            {series.count} / {series.span_minutes}m
          </div>
        </div>
      </div>
    </div>
  );
}
