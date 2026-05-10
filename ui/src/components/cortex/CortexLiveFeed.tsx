// BlackBoard/ui/src/components/cortex/CortexLiveFeed.tsx
// @ai-rules:
// 1. [Pattern]: Scrolling log of cortex_thinking WS messages. Auto-scrolls to bottom.
// 2. [Constraint]: Color-coded by content_type: text=gray, tool_call=blue, tool_result=green.
// 3. [Pattern]: Shows placeholder when System 2 is not active (no entries received).
// 4. [Pattern]: Mode indicator derived from whisper presence -- [shadow] if no whispers, [live] if whispers exist.
import { useEffect, useRef, type FC } from 'react';
import { Brain, Wrench, CheckCircle, Shield, Zap } from 'lucide-react';
import type { CortexThinkingMessage, WhisperMessage } from './types';

interface CortexLiveFeedProps {
  entries: CortexThinkingMessage[];
  whispers?: WhisperMessage[];
  className?: string;
}

const TYPE_STYLES: Record<string, { color: string; icon: typeof Brain }> = {
  text:        { color: 'text-text-muted',   icon: Brain },
  tool_call:   { color: 'text-blue-400',     icon: Wrench },
  tool_result: { color: 'text-emerald-400',  icon: CheckCircle },
};

const CortexLiveFeed: FC<CortexLiveFeedProps> = ({ entries, whispers = [], className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const hasWhispers = whispers.length > 0;
  const mode = hasWhispers ? 'live' : 'shadow';

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries.length, whispers.length]);

  if (entries.length === 0 && whispers.length === 0) {
    return (
      <div className={`flex items-center justify-center text-text-muted text-xs py-6 ${className ?? ''}`}>
        <Brain size={14} className="mr-2 opacity-50" />
        No Cortex observer active
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`overflow-y-auto text-xs font-mono space-y-0.5 ${className ?? ''}`}>
      {/* Mode indicator */}
      <div className="flex items-center gap-1.5 px-2 py-1 border-b border-border/50 mb-1">
        {mode === 'shadow' ? (
          <>
            <Shield size={10} className="text-amber-500" />
            <span className="text-amber-500/80 text-[10px]">[shadow] Observing only</span>
          </>
        ) : (
          <>
            <Zap size={10} className="text-blue-400" />
            <span className="text-blue-400/80 text-[10px]">[live] Active interventions</span>
          </>
        )}
      </div>

      {entries.map((entry, i) => {
        const style = TYPE_STYLES[entry.content_type] ?? TYPE_STYLES.text;
        const Icon = style.icon;
        const text = entry.text ?? entry.tool ?? entry.result_preview ?? '';
        const isShadow = entry.content_type === 'tool_call';

        return (
          <div key={`t-${i}`} className={`flex items-start gap-1.5 px-2 py-0.5 ${style.color}`}>
            <Icon size={11} className="mt-0.5 flex-shrink-0" />
            <span className="break-all">
              {entry.content_type === 'tool_call' && (
                <span className="text-blue-300 font-semibold">{entry.tool} </span>
              )}
              {text}
              {isShadow && <span className="ml-1 text-amber-500/60">[shadow]</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default CortexLiveFeed;
