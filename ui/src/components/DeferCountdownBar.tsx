// BlackBoard/ui/src/components/DeferCountdownBar.tsx
// @ai-rules:
// 1. [Pattern]: Shrinking progress bar = remaining defer time (full → empty).
// 2. [Constraint]: WCAG progressbar role; compact mode for sidebar tree rows.
// 3. [Pattern]: Purple deferred tokens from STATUS_COLORS.deferred.

import { Clock } from 'lucide-react';
import type { ConversationTurn } from '../api/types';
import { STATUS_COLORS } from '../constants/colors';
import { useDeferCountdown } from '../hooks/useDeferCountdown';

const DEFER = STATUS_COLORS.deferred;

export default function DeferCountdownBar({
  deferUntil,
  deferStartedAt,
  conversation,
  compact = false,
  className = '',
}: {
  deferUntil?: number;
  deferStartedAt?: number;
  conversation?: ConversationTurn[];
  compact?: boolean;
  className?: string;
}) {
  const { timeline, ratio, remainingLabel, expired, ariaValueNow, ariaValueMax } = useDeferCountdown(
    deferUntil,
    deferStartedAt,
    conversation,
    true,
  );

  if (!timeline) return null;

  const trackH = compact ? 'h-1' : 'h-1.5';
  const textSize = compact ? 'text-[10px]' : 'text-[11px]';

  return (
    <div className={`w-full min-w-0 ${className}`}>
      <div className={`flex items-center justify-between gap-1.5 mb-0.5 ${textSize}`}>
        <span className="flex items-center gap-1 text-text-muted truncate">
          <Clock size={compact ? 10 : 12} className="flex-shrink-0" style={{ color: DEFER.border }} aria-hidden />
          <span className="truncate">{expired ? 'Defer ended' : 'Deferred'}</span>
        </span>
        <span
          className="font-mono tabular-nums flex-shrink-0"
          style={{ color: expired ? '#fbbf24' : DEFER.text }}
        >
          {remainingLabel}
        </span>
      </div>
      <div
        className={`w-full rounded-full overflow-hidden bg-bg-tertiary ${trackH}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={ariaValueMax}
        aria-valuenow={ariaValueNow}
        aria-label={
          expired
            ? 'Defer period ended, waiting for FRIDAY to resume'
            : `Defer time remaining: ${remainingLabel}`
        }
      >
        <div
          className={`${trackH} rounded-full transition-[width] duration-1000 ease-linear`}
          style={{
            width: `${Math.round(ratio * 100)}%`,
            background: expired
              ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
              : `linear-gradient(90deg, ${DEFER.border}, ${DEFER.text})`,
            boxShadow: expired ? '0 0 8px #f59e0b40' : ratio < 0.15 ? `0 0 6px ${DEFER.border}60` : 'none',
          }}
        />
      </div>
    </div>
  );
}
