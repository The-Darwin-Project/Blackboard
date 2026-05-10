// BlackBoard/ui/src/components/cortex/PulseTimeline.tsx
// @ai-rules:
// 1. [Pattern]: Horizontal timeline of pulse batches rendered as dots. Pure div-based (no recharts).
// 2. [Constraint]: Dot position = (batch.timestamp - start) / (now - start) as percentage.
// 3. [Pattern]: Click dot -> onSelectBatch callback highlights fired neurons in graph.
import { useMemo, type FC } from 'react';
import { NEURON_COLORS } from '../../constants/colors';
import type { PulseBatch } from './types';

interface PulseTimelineProps {
  batches: PulseBatch[];
  eventCreatedAt?: number;
  onSelectBatch?: (batch: PulseBatch) => void;
  className?: string;
}

const PulseTimeline: FC<PulseTimelineProps> = ({ batches, eventCreatedAt, onSelectBatch, className }) => {
  const start = eventCreatedAt ?? (batches[0]?.timestamp ?? Date.now() / 1000);
  const now = Date.now() / 1000;
  const span = Math.max(now - start, 60);

  const dots = useMemo(() =>
    batches.map((b, i) => {
      const pct = Math.min(((b.timestamp - start) / span) * 100, 100);
      const dominantType = b.pulses[0]?.neuron_type ?? 'tool';
      const size = Math.min(4 + b.pulses.length * 2, 14);
      return { key: i, pct, color: NEURON_COLORS[dominantType] ?? '#6b7280', size, batch: b };
    }),
  [batches, start, span]);

  const elapsed = Math.round(span / 60);

  return (
    <div className={`flex flex-col gap-1 ${className ?? ''}`}>
      <div className="text-[10px] text-text-muted flex justify-between px-1">
        <span>t=0</span>
        <span>{elapsed}m</span>
      </div>
      <div className="relative h-5 bg-bg-tertiary rounded-full overflow-hidden">
        {dots.map(d => (
          <button
            key={d.key}
            onClick={() => onSelectBatch?.(d.batch)}
            className="absolute top-1/2 -translate-y-1/2 rounded-full transition-transform hover:scale-150"
            style={{
              left: `${d.pct}%`,
              width: d.size,
              height: d.size,
              backgroundColor: d.color,
              opacity: 0.85,
            }}
            title={`Turn ${d.batch.turn} — ${d.batch.pulses.length} neurons`}
          />
        ))}
      </div>
    </div>
  );
};

export default PulseTimeline;
