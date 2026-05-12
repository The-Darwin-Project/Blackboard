// BlackBoard/ui/src/hooks/useCortexData.ts
// @ai-rules:
// 1. [Pattern]: TanStack Query for REST, useWSMessage for real-time pulses.
// 2. [Constraint]: getCognitiveGraph and getPulses are fetched via fetchApi pattern from client.ts.
// 3. [Pattern]: usePulseStream accumulates batches in a ref to avoid re-renders on every pulse.
import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useWSMessage, useWSReconnect } from '../contexts/WebSocketContext';
import { getCognitiveGraph, getCortexActivity, getRecentPulses } from '../api/client';
import type {
  CognitiveGraphResponse, PulseBatch, CortexThinkingMessage,
  CortexShadowMessage, CortexStatusMessage, CortexHeartbeatMessage,
  WhisperMessage, FrictionIndicator,
} from '../components/cortex/types';

export function useCortexGraph() {
  return useQuery<CognitiveGraphResponse>({
    queryKey: ['cognitive-graph'],
    queryFn: getCognitiveGraph,
    staleTime: 60_000,
  });
}

export function useRecentPulses() {
  return useQuery<PulseBatch[]>({
    queryKey: ['recent-pulses'],
    queryFn: () => getRecentPulses(5 * 60),
    staleTime: 30_000,
  });
}

export function usePulseStream() {
  const [batches, setBatches] = useState<PulseBatch[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

  const backfill = useCallback(() => {
    getCortexActivity().then(recent => {
      if (recent.length === 0) return;
      setBatches(prev => {
        const merged = [...prev];
        for (const b of recent) {
          const id = b._stream_id || `${b.event_id}:${b.timestamp}`;
          if (!seenIds.current.has(id)) {
            seenIds.current.add(id);
            merged.push(b);
          }
        }
        if (seenIds.current.size > 500) {
          const entries = [...seenIds.current];
          seenIds.current = new Set(entries.slice(-300));
        }
        return merged.slice(-200);
      });
    }).catch(() => {});
  }, []);

  // Backfill on mount
  useEffect(() => { backfill(); }, [backfill]);

  // Backfill on WS reconnect
  useWSReconnect(backfill);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'pulse_batch' && msg.batch) {
      const batch = msg.batch as PulseBatch;
      const id = batch._stream_id || `${batch.event_id}:${batch.timestamp}`;
      if (seenIds.current.has(id)) return;
      seenIds.current.add(id);
      setBatches(prev => [...prev.slice(-200), batch]);
    }
  }, []));

  return batches;
}

export function useCortexThinking() {
  const [entries, setEntries] = useState<CortexThinkingMessage[]>([]);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'cortex_thinking') {
      setEntries(prev => [...prev.slice(-100), msg as unknown as CortexThinkingMessage]);
    }
  }, []));

  return entries;
}

export function useCortexShadow() {
  const [shadows, setShadows] = useState<CortexShadowMessage[]>([]);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'cortex_shadow') {
      setShadows(prev => [...prev.slice(-50), msg as unknown as CortexShadowMessage]);
    }
  }, []));

  return shadows;
}

/** Track which neurons were recently pulsed for glow animation */
export function usePulseGlow() {
  const glowMapRef = useRef<Map<string, number>>(new Map());
  const [glowTick, setGlowTick] = useState(0);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'pulse_batch' && msg.batch) {
      const batch = msg.batch as PulseBatch;
      const now = Date.now();
      for (const p of batch.pulses) {
        glowMapRef.current.set(p.neuron_id, now);
      }
      setGlowTick(t => t + 1);
    }
  }, []));

  const isGlowing = useCallback((neuronId: string) => {
    const t = glowMapRef.current.get(neuronId);
    return t ? Date.now() - t < 2000 : false;
  }, [glowTick]); // eslint-disable-line react-hooks/exhaustive-deps

  return { isGlowing, glowTick };
}

export function useCortexStatus() {
  const [status, setStatus] = useState<CortexStatusMessage | null>(null);

  useEffect(() => {
    fetch('/api/cortex/status')
      .then(r => r.json())
      .then((data: { status?: string; model?: string; shadow?: boolean }) => {
        if (data.status && data.status !== 'disabled') {
          setStatus({
            type: 'cortex_status',
            status: data.status as 'watching' | 'disconnected',
            model: data.model ?? '',
            shadow: data.shadow ?? false,
            timestamp: Date.now() / 1000,
          });
        }
      })
      .catch(() => {});
  }, []);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'cortex_status') {
      setStatus(msg as unknown as CortexStatusMessage);
    }
  }, []));

  return status;
}

export function useHeartbeat() {
  const [heartbeatType, setHeartbeatType] = useState<'spike' | 'wave' | null>(null);
  const [tick, setTick] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'cortex_heartbeat') {
      const hb = msg as unknown as CortexHeartbeatMessage;
      setHeartbeatType(hb.heartbeat);
      setTick(t => t + 1);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setHeartbeatType(null), 3000);
    }
  }, []));

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  return { heartbeatType, tick };
}

export function useCortexWhispers() {
  const [whispers, setWhispers] = useState<WhisperMessage[]>([]);

  useWSMessage(useCallback((msg) => {
    if (msg.type === 'whisper') {
      setWhispers(prev => [...prev.slice(-50), msg as unknown as WhisperMessage]);
    }
  }, []));

  return whispers;
}

const SPIRAL_THRESHOLD = 5;
const PLATEAU_SECONDS = 1800;

export function useFrictionIndicators(eventId: string, batches: PulseBatch[]): FrictionIndicator[] {
  return useMemo(() => {
    const eventBatches = batches.filter(b => b.event_id === eventId);
    if (eventBatches.length === 0) return [];

    const indicators: FrictionIndicator[] = [];

    // Spiral: same non-defer tool neuron fires 5+ times with no phase pulse
    const toolCounts = new Map<string, number>();
    let hasPhase = false;
    for (const b of eventBatches) {
      for (const p of b.pulses) {
        if (p.neuron_type === 'tool' && p.neuron_id !== 'tool:defer_event') toolCounts.set(p.neuron_id, (toolCounts.get(p.neuron_id) ?? 0) + 1);
        if (p.neuron_type === 'phase') hasPhase = true;
      }
    }
    if (!hasPhase) {
      for (const [, count] of toolCounts) {
        if (count >= SPIRAL_THRESHOLD) {
          indicators.push({ pattern: 'spiral', label: 'Spiral', color: 'red' });
          break;
        }
      }
    }

    // Plateau: active processing (not deferred) with no phase change
    const now = Date.now() / 1000;
    const activeBatches = eventBatches.filter(
      b => b.timestamp > now - PLATEAU_SECONDS && !b.pulses.some(p => p.neuron_id === 'tool:defer_event'),
    );
    const recentPhase = activeBatches.some(b => b.pulses.some(p => p.neuron_type === 'phase'));
    if (activeBatches.length > 0 && !recentPhase) {
      indicators.push({ pattern: 'plateau', label: 'Plateau', color: 'amber' });
    }

    // Agent Churn: 3+ different agents with same knowledge neurons
    const agentKnowledge = new Map<string, Set<string>>();
    for (const b of eventBatches) {
      const agents = b.pulses.filter(p => p.neuron_type === 'agent').map(p => p.neuron_id);
      const knowledge = b.pulses.filter(p => p.neuron_type === 'lesson' || p.neuron_type === 'memory').map(p => p.neuron_id);
      for (const a of agents) {
        if (!agentKnowledge.has(a)) agentKnowledge.set(a, new Set());
        for (const k of knowledge) agentKnowledge.get(a)!.add(k);
      }
    }
    if (agentKnowledge.size >= 3) {
      const allKnowledge = [...agentKnowledge.values()];
      const shared = [...allKnowledge[0]].filter(k => allKnowledge.every(s => s.has(k)));
      if (shared.length > 0) {
        indicators.push({ pattern: 'agent_churn', label: 'Agent Churn', color: 'amber' });
      }
    }

    return indicators;
  }, [eventId, batches]);
}
