// BlackBoard/ui/src/components/cortex/CortexPage.tsx
// @ai-rules:
// 1. [Pattern]: Split layout -- left panel (global topology), right panel (drill-down on event select).
// 2. [Pattern]: Active events bar at bottom of left panel. Click event -> opens drill-down.
// 3. [Constraint]: Uses useCortexGraph for initial load, usePulseStream for real-time, usePulseGlow for animation.
import { useState, useMemo, useCallback, type FC } from 'react';
import { Loader2, Brain, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCortexGraph, usePulseStream, usePulseGlow, useCortexThinking, useCortexShadow, useCortexWhispers } from '../../hooks/useCortexData';
import { useActiveEvents } from '../../hooks/useQueue';
import CortexGraph from './CortexGraph';
import CortexLiveFeed from './CortexLiveFeed';
import EventDrillDown from './EventDrillDown';
import type { Neuron } from './types';

const CortexPage: FC = () => {
  const { data: graphData, isLoading, error } = useCortexGraph();
  const liveBatches = usePulseStream();
  const { isGlowing, glowTick } = usePulseGlow();
  const thinkingEntries = useCortexThinking();
  const shadowEntries = useCortexShadow();
  const whisperEntries = useCortexWhispers();
  const { data: activeEvents } = useActiveEvents();

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [feedOpen, setFeedOpen] = useState(true);

  const neurons: Neuron[] = graphData?.neurons ?? [];

  const glowingIds = useMemo(() => {
    const ids = new Set<string>();
    for (const n of neurons) {
      if (isGlowing(n.id)) ids.add(n.id);
    }
    return ids;
  }, [neurons, isGlowing, glowTick]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectEvent = useCallback((id: string) => {
    setSelectedEventId(prev => prev === id ? null : id);
  }, []);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted">
        <Loader2 size={20} className="animate-spin mr-2" />
        Loading neural topology…
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center text-red-400 text-sm">
        Failed to load cognitive graph: {(error as Error).message}
      </div>
    );
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* Center: Graph + events bar */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <CortexGraph
          neurons={neurons}
          glowingIds={glowingIds}
          activeEvents={activeEvents ?? []}
          liveBatches={liveBatches}
          className="flex-1 min-h-0"
          onClickNeuron={(_id) => {
            // Future: neuron detail tooltip
          }}
        />

        {/* Active events bar */}
        <div className="flex-shrink-0 border-t border-border px-3 py-1.5 flex items-center gap-1.5 overflow-x-auto">
          <Brain size={12} className="text-text-muted flex-shrink-0" />
          {(!activeEvents || activeEvents.length === 0) && (
            <span className="text-[10px] text-text-muted">No active events</span>
          )}
          {activeEvents?.map(evt => {
            const isActive = selectedEventId === evt.id;
            const hasPulse = liveBatches.some(b => b.event_id === evt.id);
            const hasShadow = shadowEntries.some(s => s.event_id === evt.id);
            const hasWhisper = whisperEntries.some(w => w.event_id === evt.id);
            const hasAlert = whisperEntries.some(w => w.event_id === evt.id && w.severity === 'alert');
            return (
              <button
                key={evt.id}
                onClick={() => handleSelectEvent(evt.id)}
                className={`relative px-2 py-1 rounded text-[10px] font-mono transition-colors flex-shrink-0 ${
                  isActive
                    ? 'bg-accent/20 text-accent border border-accent/40'
                    : 'bg-bg-tertiary text-text-secondary hover:bg-bg-secondary border border-transparent'
                }`}
              >
                {evt.id.slice(0, 8)}
                {hasPulse && <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                {(hasShadow || hasWhisper) && (
                  <span className={`absolute -top-1 -right-1 w-2 h-2 rounded-full ${
                    hasAlert ? 'bg-red-500' : hasWhisper ? 'bg-red-400' : 'bg-amber-400'
                  }`} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Right panel: collapsible Cortex Live Feed + Event drill-down */}
      <div className={`flex-shrink-0 flex flex-col border-l border-border transition-all duration-300 ${
        feedOpen ? 'w-96' : 'w-10'
      }`}>
        {/* Collapse toggle -- sticky header */}
        <button
          onClick={() => setFeedOpen(prev => !prev)}
          className="flex-shrink-0 z-10 flex items-center gap-1.5 px-3 py-2 bg-bg-primary text-text-muted hover:text-text-primary transition-colors border-b border-border"
          title={feedOpen ? 'Collapse Cortex panel' : 'Expand Cortex panel'}
        >
          {feedOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          {feedOpen && <span className="text-[11px] font-semibold uppercase tracking-wider">Cortex</span>}
        </button>

        {feedOpen && (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Event drill-down (when selected) */}
            {selectedEventId && (
              <div className="flex-1 min-h-0 overflow-y-auto border-b border-border">
                <EventDrillDown
                  eventId={selectedEventId}
                  allNeurons={neurons}
                  liveBatches={liveBatches}
                  thinkingEntries={thinkingEntries}
                  shadowEntries={shadowEntries}
                  whisperEntries={whisperEntries}
                  glowingIds={glowingIds}
                  onClose={() => setSelectedEventId(null)}
                />
              </div>
            )}

            {/* Live Feed -- only when no event selected (drill-down has its own) */}
            {!selectedEventId && (
              <div className="flex-1 min-h-0 overflow-y-auto">
                <CortexLiveFeed
                  entries={thinkingEntries}
                  className="h-full"
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CortexPage;
