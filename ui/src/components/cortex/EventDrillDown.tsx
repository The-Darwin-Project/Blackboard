// BlackBoard/ui/src/components/cortex/EventDrillDown.tsx
// @ai-rules:
// 1. [Pattern]: Right panel shown when an event is selected from active events bar.
// 2. [Pattern]: Same CortexGraph but dimmed -- only neurons fired during THIS event are bright.
// 3. [Constraint]: Uses getEventPulses for historical data + live pulse stream filtered by event_id.
// 4. [Pattern]: Friction indicators derived client-side from pulse data (spiral/plateau/agent_churn).
// 5. [Pattern]: Cortex Observations section merges shadow + live whisper entries with [shadow]/[live] badges.
import { useMemo, type FC } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Clock, Layers, Zap, AlertTriangle } from 'lucide-react';
import { getEventPulses } from '../../api/client';
import { PHASE_COLORS, ACTOR_COLORS } from '../../constants/colors';
// CortexGraph removed from drill-down to reduce GPU load (single graph in main view)
import PulseTimeline from './PulseTimeline';
import CortexLiveFeed from './CortexLiveFeed';
import { useFrictionIndicators } from '../../hooks/useCortexData';
import type { Neuron, PulseBatch, CortexThinkingMessage, CortexShadowMessage, WhisperMessage } from './types';

const WHISPER_COLORS: Record<string, string> = {
  nudge: 'bg-slate-500/20 text-slate-400',
  course_correct: 'bg-amber-500/20 text-amber-400',
  alert: 'bg-red-500/20 text-red-400',
};

const FRICTION_COLORS: Record<string, string> = {
  red: 'bg-red-500/20 text-red-400 border-red-500/30',
  amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
};

interface EventDrillDownProps {
  eventId: string;
  allNeurons: Neuron[];
  liveBatches: PulseBatch[];
  thinkingEntries: CortexThinkingMessage[];
  shadowEntries: CortexShadowMessage[];
  whisperEntries: WhisperMessage[];
  glowingIds: Set<string>;
  onClose: () => void;
}

const EventDrillDown: FC<EventDrillDownProps> = ({
  eventId, liveBatches, thinkingEntries, shadowEntries, whisperEntries, onClose,
}) => {
  const { data: historicalBatches } = useQuery({
    queryKey: ['event-pulses', eventId],
    queryFn: () => getEventPulses(eventId),
    staleTime: 10_000,
  });

  const eventBatches = useMemo(() => {
    const hist = historicalBatches ?? [];
    const live = liveBatches.filter(b => b.event_id === eventId);
    const seen = new Set(hist.map(b => `${b.timestamp}-${b.turn}`));
    const deduped = [...hist];
    for (const b of live) {
      if (!seen.has(`${b.timestamp}-${b.turn}`)) deduped.push(b);
    }
    return deduped.sort((a, b) => a.timestamp - b.timestamp);
  }, [historicalBatches, liveBatches, eventId]);

  void useMemo(() => {
    // placeholder -- firedIds available for future use
    return eventBatches.length;
  }, [eventBatches]);


  // Tool trail
  const toolTrail = useMemo(() => {
    const tools: { name: string; turn: number }[] = [];
    for (const b of eventBatches) {
      for (const p of b.pulses) {
        if (p.neuron_type === 'tool') tools.push({ name: p.neuron_id.replace('tool:', ''), turn: b.turn });
      }
    }
    return tools.slice(-10);
  }, [eventBatches]);

  // Agent trail
  const agentTrail = useMemo(() => {
    const agents: string[] = [];
    for (const b of eventBatches) {
      for (const p of b.pulses) {
        if (p.neuron_type === 'agent') agents.push(p.neuron_id.replace('agent:', ''));
      }
    }
    return [...new Set(agents)];
  }, [eventBatches]);

  // Co-firing clusters
  const coFiring = useMemo(() => {
    const pairCount = new Map<string, number>();
    for (const b of eventBatches) {
      const ids = b.pulses.filter(p => p.neuron_type === 'lesson' || p.neuron_type === 'memory').map(p => p.neuron_id);
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const key = [ids[i], ids[j]].sort().join('|');
          pairCount.set(key, (pairCount.get(key) ?? 0) + 1);
        }
      }
    }
    return [...pairCount.entries()]
      .filter(([, c]) => c >= 2)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([pair, count]) => ({ pair: pair.split('|'), count }));
  }, [eventBatches]);

  const eventThinking = useMemo(
    () => thinkingEntries.filter(e => e.event_id === eventId),
    [thinkingEntries, eventId],
  );

  const eventShadow = useMemo(
    () => shadowEntries.filter(e => e.event_id === eventId),
    [shadowEntries, eventId],
  );

  const eventWhispers = useMemo(
    () => whisperEntries.filter(e => e.event_id === eventId),
    [whisperEntries, eventId],
  );

  const frictionIndicators = useFrictionIndicators(eventId, liveBatches);

  const latestPhase = useMemo(() => {
    for (let i = eventBatches.length - 1; i >= 0; i--) {
      const ph = eventBatches[i].pulses.find(p => p.neuron_type === 'phase');
      if (ph) return ph.neuron_id.replace('phase:', '');
    }
    return null;
  }, [eventBatches]);

  const elapsed = eventBatches.length > 0
    ? Math.round((Date.now() / 1000 - eventBatches[0].timestamp) / 60)
    : 0;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-3 py-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-text-primary font-mono font-semibold">{eventId.slice(0, 12)}</span>
          {latestPhase && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium"
              style={{
                backgroundColor: PHASE_COLORS[latestPhase]?.bg ?? '#1e293b',
                color: PHASE_COLORS[latestPhase]?.text ?? '#94a3b8',
              }}>
              {latestPhase}
            </span>
          )}
          <span className="text-text-muted flex items-center gap-1">
            <Clock size={10} /> {elapsed}m
          </span>
          <span className="text-text-muted flex items-center gap-1">
            <Layers size={10} /> {eventBatches.length} pulses
          </span>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-secondary">
          <X size={14} />
        </button>
      </div>

      {/* Details */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
        {/* Tool trail */}
        <section>
          <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Tool Trail</h4>
          <div className="flex flex-wrap gap-1">
            {toolTrail.map((t, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-bg-tertiary text-[10px] text-slate-300 font-mono">
                <Zap size={8} className="text-slate-500" />
                {t.name}
              </span>
            ))}
          </div>
        </section>

        {/* Agent trail */}
        {agentTrail.length > 0 && (
          <section>
            <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Agents</h4>
            <div className="flex gap-1">
              {agentTrail.map(a => (
                <span key={a} className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                  style={{ backgroundColor: `${ACTOR_COLORS[a] ?? '#6b7280'}20`, color: ACTOR_COLORS[a] ?? '#94a3b8' }}>
                  {a}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Pulse timeline */}
        <section>
          <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pulse Timeline</h4>
          <PulseTimeline
            batches={eventBatches}
            eventCreatedAt={eventBatches[0]?.timestamp}
          />
        </section>

        {/* Co-firing clusters */}
        {coFiring.length > 0 && (
          <section>
            <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Co-firing Clusters</h4>
            <div className="space-y-0.5">
              {coFiring.map((cf, i) => (
                <div key={i} className="text-[10px] text-text-secondary">
                  <span className="font-mono text-emerald-400">{cf.pair.map(p => p.split(':')[1]?.slice(0, 8)).join(' + ')}</span>
                  <span className="text-text-muted ml-1">fired {cf.count}x together</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Friction indicators */}
        {frictionIndicators.length > 0 && (
          <section>
            <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1 flex items-center gap-1">
              <AlertTriangle size={10} /> Friction Indicators
            </h4>
            <div className="flex flex-wrap gap-1">
              {frictionIndicators.map(fi => (
                <span key={fi.pattern}
                  className={`text-xs px-2 py-0.5 rounded-full border font-medium ${FRICTION_COLORS[fi.color]}`}>
                  {fi.label}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Cortex observations (shadow + live whispers) */}
        {(eventShadow.length > 0 || eventWhispers.length > 0) && (
          <section>
            <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Cortex Observations</h4>
            <div className="space-y-1">
              {eventShadow.map((s, i) => (
                <div key={`s-${i}`} className="text-[10px] text-amber-400/80 bg-amber-900/10 px-2 py-1 rounded">
                  <span className="bg-amber-500/20 text-amber-400 text-[9px] px-1 py-0.5 rounded mr-1">[shadow]</span>
                  <span className="font-semibold">{s.tool}</span>{' '}
                  {(s.args?.message as string) ?? (s.args?.context as string) ?? (s.args?.insight as string) ?? JSON.stringify(s.args)}
                </div>
              ))}
              {eventWhispers.map((w, i) => (
                <div key={`w-${i}`} className={`text-[10px] px-2 py-1 rounded ${WHISPER_COLORS[w.severity]}`}>
                  <span className="bg-blue-500/20 text-blue-400 text-[9px] px-1 py-0.5 rounded mr-1">[live]</span>
                  <span className={`text-[9px] px-1 py-0.5 rounded mr-1 ${WHISPER_COLORS[w.severity]}`}>
                    {w.severity}
                  </span>
                  {w.insight.slice(0, 150)}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Live feed */}
        <section>
          <h4 className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Cortex Live Feed</h4>
          <CortexLiveFeed entries={eventThinking} className="max-h-40 bg-bg-tertiary rounded p-1" />
        </section>
      </div>
    </div>
  );
};

export default EventDrillDown;
