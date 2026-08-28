// BlackBoard/ui/src/components/cortex/CortexPage.tsx
// @ai-rules:
// 1. [Pattern]: Split layout -- left panel (global topology), right panel (drill-down on event select).
// 2. [Pattern]: Active events bar at bottom of left panel. Click event -> opens drill-down.
// 3. [Constraint]: Uses useCortexGraph for initial load, usePulseStream for real-time, usePulseGlow for animation.
// 4. [Pattern]: Lookup search box (top-left overlay) queries GET /queue/admin/{collection}/{id}
//    directly -- finds facts/lessons/memories NOT on the 600/type ring sample without growing the
//    ring itself. If the resolved neuron is already on-graph, selects it in place; otherwise opens
//    NeuronInfoPanel with the fetched payload via the `lookupNeuron` fallback (off-graph render path).
import { useState, useMemo, useCallback, useEffect, type FC } from 'react';
import { Loader2, Brain, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { useCortexGraph, useKGServiceDetail, useKGServices, usePulseStream, usePulseGlow, useCortexThinking, useCortexShadow, useCortexWhispers, useCortexStatus, useHeartbeat } from '../../hooks/useCortexData';
import { useActiveEvents } from '../../hooks/useQueue';
import { getEventReport, getKnowledgeById, getLessonById, getMemory } from '../../api/client';
import CortexGraph from './CortexGraph';
import CortexLiveFeed from './CortexLiveFeed';
import EventDrillDown from './EventDrillDown';
import NeuronInfoPanel from './NeuronInfoPanel';
import MarkdownViewer from '../MarkdownViewer';
import { getExecutiveNeurons } from './cortex-constants';
import type { Neuron } from './types';

type OffRingCollection = 'knowledge' | 'lesson' | 'memory';

function isOffRingCollection(value: string): value is OffRingCollection {
  return value === 'knowledge' || value === 'lesson' || value === 'memory';
}

async function fetchOffRingNeuron(collection: OffRingCollection, id: string): Promise<Neuron> {
  if (collection === 'knowledge') {
    const point = await getKnowledgeById(id);
    return { id: `knowledge:${point.id}`, type: 'knowledge', heat: 0, payload: point.payload as unknown as Record<string, unknown> };
  }
  if (collection === 'lesson') {
    const lesson = await getLessonById(id);
    return { id: `lesson:${lesson.id}`, type: 'lesson', heat: 0, payload: lesson.payload as unknown as Record<string, unknown> };
  }
  const memory = await getMemory(id);
  return { id: `memory:${memory.id}`, type: 'memory', heat: 0, payload: memory.payload as Record<string, unknown> };
}

const CortexPage: FC = () => {
  const { data: graphData, isLoading, error } = useCortexGraph();
  const liveBatches = usePulseStream();
  const { isGlowing, glowTick } = usePulseGlow();
  const thinkingEntries = useCortexThinking();
  const shadowEntries = useCortexShadow();
  const whisperEntries = useCortexWhispers();
  const cortexStatus = useCortexStatus();
  const { heartbeatType, tick: heartbeatTick } = useHeartbeat();
  const { data: activeEvents } = useActiveEvents();
  const { data: kgServices } = useKGServices();

  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [selectedNeuron, setSelectedNeuron] = useState<{ id: string; pos: { x: number; y: number } } | null>(null);
  const [feedOpen, setFeedOpen] = useState(true);
  const [reportViewer, setReportViewer] = useState<{ title: string; content: string } | null>(null);
  const [lookupNeuron, setLookupNeuron] = useState<Neuron | null>(null);
  const [lookupCollection, setLookupCollection] = useState<'knowledge' | 'lesson' | 'memory'>('knowledge');
  const [lookupId, setLookupId] = useState('');
  const [lookupError, setLookupError] = useState<string | null>(null);

  const selectedServiceId = selectedNeuron?.id.startsWith('service:')
    ? selectedNeuron.id
    : null;
  const { data: serviceDetail } = useKGServiceDetail(selectedServiceId);

  const neurons: Neuron[] = graphData?.neurons ?? [];

  const mergedNeurons = useMemo(() => {
    const executive = getExecutiveNeurons();
    const heatMap = new Map(neurons.map(n => [n.id, n.heat]));
    for (const n of executive) {
      if (heatMap.has(n.id)) n.heat = heatMap.get(n.id)!;
    }
    return [...neurons, ...executive];
  }, [neurons]);

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

  const handleClickNeuron = useCallback((id: string | null, pos?: { x: number; y: number }) => {
    if (id === null) { setSelectedNeuron(null); return; }
    // Event nodes: fetch report and show in floating viewer
    if (activeEvents?.some(e => e.id === id)) {
      setSelectedEventId(prev => prev === id ? null : id);
      getEventReport(id)
        .then(data => setReportViewer({ title: `Report: ${id.slice(0, 12)}`, content: data.markdown }))
        .catch(() => {});
      return;
    }
    // Service nodes are dynamically added by CortexGraph — synthesize a Neuron for the panel
    if (id.startsWith('service:')) {
      setSelectedNeuron(prev => prev?.id === id ? null : (pos ? { id, pos } : null));
      return;
    }
    if (mergedNeurons.some(n => n.id === id)) {
      setSelectedNeuron(prev => prev?.id === id ? null : (pos ? { id, pos } : null));
      return;
    }
    // Live pulse-materialized knowledge-ring nodes (see cortex-pulse-handler.ts's
    // materializeNeuron) exist on the Sigma graph but not yet in the REST-fetched
    // mergedNeurons -- resolve them the same way the manual off-ring lookup box does.
    const [neuronType, ...rest] = id.split(':');
    const rawId = rest.join(':');
    if (!rawId || !isOffRingCollection(neuronType)) return;
    let closed = false;
    setSelectedNeuron(prev => {
      if (prev?.id === id) { closed = true; return null; }
      return prev;
    });
    if (closed) return;
    fetchOffRingNeuron(neuronType, rawId)
      .then(neuron => {
        setLookupNeuron(neuron);
        setSelectedNeuron(pos ? { id, pos } : null);
      })
      .catch(() => setLookupError(`No ${neuronType} found for "${rawId}"`));
  }, [mergedNeurons, activeEvents]);

  const handleCloseNeuron = useCallback(() => setSelectedNeuron(null), []);

  const handleLookup = useCallback(async () => {
    const id = lookupId.trim();
    if (!id) return;
    setLookupError(null);
    try {
      const neuron = await fetchOffRingNeuron(lookupCollection, id);
      setLookupNeuron(neuron);
      const centerPos = { x: window.innerWidth / 2 - 160, y: window.innerHeight / 2 - 100 };
      setSelectedNeuron({ id: neuron.id, pos: centerPos });
    } catch {
      setLookupError(`No ${lookupCollection} found for "${id}"`);
    }
  }, [lookupId, lookupCollection]);

  useEffect(() => {
    if (
      selectedNeuron
      && !selectedNeuron.id.startsWith('service:')
      && lookupNeuron?.id !== selectedNeuron.id
      && !mergedNeurons.some(n => n.id === selectedNeuron.id)
    ) {
      setSelectedNeuron(null);
    }
  }, [selectedNeuron, mergedNeurons, lookupNeuron]);

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
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 relative">
        <div className="absolute top-2 left-2 z-10 flex items-center gap-1 bg-bg-primary/90 border border-border rounded-lg p-1.5 shadow-lg">
          <select
            value={lookupCollection}
            onChange={e => setLookupCollection(e.target.value as 'knowledge' | 'lesson' | 'memory')}
            className="bg-bg-primary border border-border rounded px-1.5 py-1 text-[10px] text-text-secondary"
          >
            <option value="knowledge">Fact ID</option>
            <option value="lesson">Lesson ID</option>
            <option value="memory">Event ID</option>
          </select>
          <input
            value={lookupId}
            onChange={e => { setLookupId(e.target.value); setLookupError(null); }}
            onKeyDown={e => { if (e.key === 'Enter') handleLookup(); }}
            placeholder="Lookup off-ring by ID..."
            className="w-40 bg-bg-primary border border-border rounded px-2 py-1 text-[10px] text-text-primary"
          />
          <button onClick={handleLookup} className="p-1.5 rounded text-text-muted hover:text-accent hover:bg-bg-tertiary transition-colors" title="Look up">
            <Search size={12} />
          </button>
        </div>
        {lookupError && (
          <div className="absolute top-11 left-2 z-10 text-[10px] text-red-400 bg-bg-primary/90 px-2 py-1 rounded border border-red-400/30">
            {lookupError}
          </div>
        )}
        <CortexGraph
          neurons={neurons}
          glowingIds={glowingIds}
          activeEvents={activeEvents ?? []}
          liveBatches={liveBatches}
          kgServices={kgServices}
          className="flex-1 min-h-0"
          onClickNeuron={handleClickNeuron}
        />
        {selectedNeuron && (() => {
          let neuron = mergedNeurons.find(n => n.id === selectedNeuron.id);
          if (!neuron && selectedNeuron.id.startsWith('service:')) {
            const svc = kgServices?.find(s => s.entity_id === selectedNeuron.id);
            const label = selectedNeuron.id.replace('service:', '');
            neuron = {
              id: selectedNeuron.id,
              type: 'service',
              heat: 0,
              payload: { label, ...(svc?.properties ?? {}), relationship_count: svc?.relationship_count ?? 0, last_seen: svc?.last_seen ?? '' },
            };
          }
          if (!neuron && lookupNeuron?.id === selectedNeuron.id) neuron = lookupNeuron;
          return neuron ? (
            <NeuronInfoPanel
              neuron={neuron}
              position={selectedNeuron.pos}
              onClose={() => { handleCloseNeuron(); setLookupNeuron(null); }}
              serviceDetail={serviceDetail}
            />
          ) : null;
        })()}
        {reportViewer && (
          <MarkdownViewer
            filename={reportViewer.title}
            content={reportViewer.content}
            onClose={() => setReportViewer(null)}
          />
        )}

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
                  cortexStatus={cortexStatus}
                  heartbeatType={heartbeatType}
                  heartbeatTick={heartbeatTick}
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
                  whispers={whisperEntries}
                  cortexStatus={cortexStatus}
                  heartbeatType={heartbeatType}
                  heartbeatTick={heartbeatTick}
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
