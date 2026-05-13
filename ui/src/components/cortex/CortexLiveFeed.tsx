// BlackBoard/ui/src/components/cortex/CortexLiveFeed.tsx
// @ai-rules:
// 1. [Pattern]: Scrolling log of cortex_thinking WS messages. Auto-scrolls to bottom.
// 2. [Constraint]: Color-coded by content_type: text=gray, tool_call=blue, tool_result=green.
// 3. [Pattern]: Shows placeholder when System 2 is not active (no entries received).
// 4. [Pattern]: Mode indicator derived from cortexStatus prop. Per-entry [shadow] badge from backend payload.
import { useEffect, useRef, type FC } from 'react';
import { Brain, Wrench, CheckCircle, Shield, Zap } from 'lucide-react';
import CortexHeartbeat from './CortexHeartbeat';
import type { CortexThinkingMessage, CortexStatusMessage, WhisperMessage } from './types';

interface CortexLiveFeedProps {
  entries: CortexThinkingMessage[];
  whispers?: WhisperMessage[];
  cortexStatus?: CortexStatusMessage | null;
  heartbeatType?: 'spike' | 'wave' | null;
  heartbeatTick?: number;
  className?: string;
  hideStatusBar?: boolean;
}

const TYPE_STYLES: Record<string, { color: string; icon: typeof Brain }> = {
  text:        { color: 'text-text-muted',   icon: Brain },
  tool_call:   { color: 'text-blue-400',     icon: Wrench },
  tool_result: { color: 'text-emerald-400',  icon: CheckCircle },
};

const CortexLiveFeed: FC<CortexLiveFeedProps> = ({ entries, whispers = [], cortexStatus, heartbeatType, heartbeatTick, className, hideStatusBar }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const isLive = cortexStatus?.shadow === false || whispers.length > 0;

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length, whispers.length]);

  const isWatching = cortexStatus?.status === 'watching';
  const statusBar = (
    <div className={`w-full py-1.5 px-3 text-[11px] font-medium border-b ${
      isWatching
        ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
        : 'border-border bg-bg-tertiary text-text-muted'
    }`}>
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${isWatching ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
        <span>{isWatching ? 'Cortex Watching' : 'Cortex Inactive'}</span>
      </div>
    </div>
  );

  if (entries.length === 0 && whispers.length === 0) {
    return (
      <div className={`flex flex-col ${className ?? ''}`}>
        {!hideStatusBar && statusBar}
        {!hideStatusBar && <CortexHeartbeat heartbeatType={heartbeatType ?? null} isWatching={isWatching} tick={heartbeatTick ?? 0} />}
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${className ?? ''}`}>
      {!hideStatusBar && <div className="flex-shrink-0">{statusBar}</div>}
      {!hideStatusBar && <CortexHeartbeat heartbeatType={heartbeatType ?? null} isWatching={isWatching} tick={heartbeatTick ?? 0} />}
      <div ref={containerRef} className="flex-1 overflow-y-auto text-xs font-mono space-y-0.5">
      {/* Mode indicator */}
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-border/50 mb-1">
        {isLive ? (
          <>
            <Zap size={10} className="text-blue-400" />
            <span className="text-blue-400/80 text-[10px]">[live] Active interventions</span>
          </>
        ) : (
          <>
            <Shield size={10} className="text-amber-500" />
            <span className="text-amber-500/80 text-[10px]">[shadow] Observing only</span>
          </>
        )}
      </div>

      {entries.map((entry, i) => {
        const style = TYPE_STYLES[entry.content_type] ?? TYPE_STYLES.text;
        const Icon = style.icon;
        const text = entry.text ?? entry.tool ?? entry.result_preview ?? '';
        const isShadow = !!((entry as unknown) as Record<string, unknown>).shadow;

        const argsSummary = entry.content_type === 'tool_call' && entry.args
          ? Object.entries(entry.args as Record<string, unknown>)
              .filter(([k]) => k !== 'event_id')
              .map(([k, v]) => `${k}: ${String(v)}`)
              .join(' | ')
          : '';

        return (
          <div key={`t-${i}`} className={`flex items-start gap-1.5 px-2 py-0.5 ${style.color}`}>
            <Icon size={11} className="mt-0.5 flex-shrink-0" />
            <span className="break-all">
              {entry.content_type === 'tool_call' && (
                <span className="text-blue-300 font-semibold">{entry.tool} </span>
              )}
              {text}
              {argsSummary && <span className="text-slate-400 ml-1">{argsSummary}</span>}
              {isShadow && <span className="ml-1 text-amber-500/60">[shadow]</span>}
            </span>
          </div>
        );
      })}
      </div>
    </div>
  );
};

export default CortexLiveFeed;
