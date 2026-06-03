// BlackBoard/ui/src/components/cortex/CortexLiveFeed.tsx
// @ai-rules:
// 1. [Pattern]: Chat bubble layout with 5 message classes (thinking, peer_input, investigation, delivered, tool_result).
// 2. [Constraint]: Auto-scroll gated on filteredEntries.length when filters active.
// 3. [Pattern]: Filter pills with localStorage persistence. Mode indicator + shadow badge preserved.
// 4. [Pattern]: classifyCortexMessage from useCortexData drives visual styling per entry.
import { useEffect, useMemo, useRef, useState, type FC } from 'react';
import { Brain, Wrench, CheckCircle, Shield, Zap, MessageCircle, Search } from 'lucide-react';
import CortexHeartbeat from './CortexHeartbeat';
import { classifyCortexMessage } from '../../hooks/useCortexData';
import type { CortexThinkingMessage, CortexStatusMessage, WhisperMessage, MessageClass } from './types';

interface CortexLiveFeedProps {
  entries: CortexThinkingMessage[];
  whispers?: WhisperMessage[];
  cortexStatus?: CortexStatusMessage | null;
  heartbeatType?: 'spike' | 'wave' | null;
  heartbeatTick?: number;
  className?: string;
  hideStatusBar?: boolean;
}

const MESSAGE_STYLES: Record<MessageClass, { color: string; bg: string; icon: typeof Brain; align: string; border: string }> = {
  thinking:      { color: 'text-text-muted italic', bg: 'bg-bg-tertiary/50', icon: Brain, align: 'justify-start', border: 'border-transparent' },
  peer_input:    { color: 'text-blue-300', bg: 'bg-blue-500/10', icon: MessageCircle, align: 'justify-end', border: 'border-blue-500/30' },
  investigation: { color: 'text-amber-300', bg: 'bg-amber-500/10', icon: Search, align: 'justify-start', border: 'border-amber-500/20' },
  delivered:     { color: 'text-emerald-300', bg: 'bg-emerald-500/10', icon: CheckCircle, align: 'justify-start', border: 'border-emerald-500/40' },
  tool_result:   { color: 'text-slate-400', bg: 'bg-bg-tertiary/30', icon: Wrench, align: 'justify-start', border: 'border-transparent' },
};

type FilterKey = 'all' | 'thinking' | 'tools' | 'delivered';
const FILTER_PILLS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'thinking', label: 'Thinking' },
  { key: 'tools', label: 'Tools' },
  { key: 'delivered', label: 'Delivered' },
];

const STORAGE_KEY = 'cortex-feed-filter';

function getStoredFilter(): FilterKey {
  try { return (localStorage.getItem(STORAGE_KEY) as FilterKey) || 'all'; } catch { return 'all'; }
}

const CortexLiveFeed: FC<CortexLiveFeedProps> = ({ entries, whispers = [], cortexStatus, heartbeatType, heartbeatTick, className, hideStatusBar }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const isLive = cortexStatus?.shadow === false || whispers.length > 0;
  const [filter, setFilter] = useState<FilterKey>(getStoredFilter);

  const classifiedEntries = useMemo(() =>
    entries.map(entry => ({ entry, msgClass: classifyCortexMessage(entry) })),
    [entries],
  );

  const filteredEntries = useMemo(() => {
    if (filter === 'all') return classifiedEntries;
    return classifiedEntries.filter(({ msgClass }) => {
      if (filter === 'thinking') return msgClass === 'thinking';
      if (filter === 'tools') return msgClass === 'investigation' || msgClass === 'tool_result';
      if (filter === 'delivered') return msgClass === 'delivered' || msgClass === 'peer_input';
      return true;
    });
  }, [classifiedEntries, filter]);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filteredEntries.length, whispers.length]);

  const handleFilterChange = (key: FilterKey) => {
    setFilter(key);
    try { localStorage.setItem(STORAGE_KEY, key); } catch { /* noop */ }
  };

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

      {/* Filter pills */}
      <div className="flex-shrink-0 flex items-center gap-1 px-2 py-1.5 border-b border-border/50">
        {FILTER_PILLS.map(pill => (
          <button
            key={pill.key}
            onClick={() => handleFilterChange(pill.key)}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
              filter === pill.key
                ? 'bg-accent/20 text-accent border border-accent/40'
                : 'bg-bg-tertiary text-text-muted hover:text-text-secondary border border-transparent'
            }`}
          >
            {pill.label}
          </button>
        ))}
      </div>

      <div ref={containerRef} className="flex-1 overflow-y-auto text-xs font-mono space-y-1 p-1.5">
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

        {filteredEntries.map(({ entry, msgClass }, i) => {
          const style = MESSAGE_STYLES[msgClass];
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
            <div key={`t-${i}`} className={`flex ${style.align}`}>
              <div className={`max-w-[85%] flex items-start gap-1.5 px-2.5 py-1.5 rounded-lg border ${style.bg} ${style.border} ${style.color}`}>
                <Icon size={11} className="mt-0.5 flex-shrink-0 opacity-70" />
                <span className="break-all text-[11px] leading-relaxed">
                  {msgClass === 'peer_input' && <span className="font-semibold text-blue-400 mr-1">FRIDAY</span>}
                  {msgClass === 'investigation' && <span className="font-semibold text-amber-400 mr-1">{entry.tool}</span>}
                  {msgClass === 'delivered' && <span className="font-semibold text-emerald-400 mr-1">✓ Delivered</span>}
                  {msgClass === 'tool_result' && <span className="font-semibold text-slate-500 mr-1">Result:</span>}
                  {text}
                  {argsSummary && <span className="text-slate-500 ml-1 text-[10px]">{argsSummary}</span>}
                  {isShadow && <span className="ml-1 text-amber-500/60 text-[10px]">[shadow]</span>}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CortexLiveFeed;
