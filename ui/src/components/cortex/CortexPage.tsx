// BlackBoard/ui/src/components/cortex/CortexPage.tsx
// @ai-rules:
// 1. [Pattern]: Split layout -- left panel (global topology), right panel (drill-down on event select).
// 2. [Pattern]: Active events bar at bottom of left panel. Click event -> opens drill-down.
// 3. [Constraint]: Uses useCortexGraph for initial load, usePulseStream for real-time, usePulseGlow for animation.
import { useState, useMemo, useCallback, type FC } from 'react';
import { Loader2, Brain } from 'lucide-react';
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
      {/* Left panel: Global topology + Cortex stream */}
      <div className={`flex flex-col overflow-hidden transition-all ${selectedEventId ? 'w-1/2' : 'w-full'}`}>
        <CortexGraph
          neurons={neurons}
          glowingIds={glowingIds}
          className="flex-1 min-h-0"
          onClickNeuron={(_id) => {
            // Future: neuron detail tooltip
          }}
        />

        {/* Cortex Live Feed -- always visible */}
        <div className="flex-shrink-0 h-48 border-t border-border overflow-hidden">
          <CortexLiveFeed
            entries={thinkingEntries}
            className="h-full"
          />
        </div>

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

      {/* Right panel: Event drill-down */}
      {selectedEventId && (
        <div className="w-1/2 border-l border-border overflow-hidden">
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
    </div>
  );
};

export default CortexPage;
