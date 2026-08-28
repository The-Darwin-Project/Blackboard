// BlackBoard/ui/src/components/cortex/cortex-pulse-handler.ts
// @ai-rules:
// 1. [Constraint]: Pure functions only -- no React, no refs. Callers (CortexGraph.tsx) unwrap
//    their `useRef` Maps to `.current` before passing them in. This keeps the module unit-testable
//    without a Sigma/React harness (see cortex-pulse-handler.test.ts).
// 2. [Pattern]: KNOWLEDGE_RING mirrors the actual `RING.knowledge` band in CortexGraph.tsx
//    (560-720) -- both cold-start placement and pulse-materialize placement share this constant.
// 3. [Pattern]: typeCounts is an O(1) budget tracker (Map<neuronType, count>), incremented on
//    materialize/merge and decremented on evict -- avoids an O(n) filterNodes scan per pulse.
// 4. [Gotcha]: evictLru scans graph.nodes() (not materializedNodesRef) for the neuronType attr --
//    cold-start nodes are eviction-eligible too, not just pulse-materialized ones.
// 5. [Constraint]: Only 'lesson' | 'memory' | 'knowledge' neuron types are ring members.
//    Non-knowledge-ring pulses (tool/phase/agent/domain/skill/service) are never materialized here.
import type { MultiGraph } from 'graphology';
import { NEURON_COLORS } from '../../constants/colors';
import type { Pulse } from './types';

/** Randomized knowledge-ring radius band. Matches CortexGraph.tsx's `RING.knowledge`. */
export const KNOWLEDGE_RING = { min: 560, max: 720 } as const;

/** Default per-type budget for the knowledge ring's LRU eviction. */
export const DEFAULT_TYPE_BUDGET = 600;

const KNOWLEDGE_RING_TYPES = new Set(['lesson', 'memory', 'knowledge']);

export interface KnowledgeNodeAttributes {
  x: number;
  y: number;
  size: number;
  color: string;
  label: string;
  type: string;
  neuronType: string;
}

function knowledgeRingColor(neuronType: string): string {
  return NEURON_COLORS[neuronType] ?? '#6b7280';
}

function knowledgeRingLabel(neuronId: string): string {
  return neuronId.split(':')[1]?.slice(0, 20) || neuronId.slice(0, 12);
}

function randomKnowledgeRingPosition(): { x: number; y: number } {
  const angle = Math.random() * Math.PI * 2;
  const radius = KNOWLEDGE_RING.min + Math.random() * (KNOWLEDGE_RING.max - KNOWLEDGE_RING.min);
  return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
}

/**
 * Materialize a missing knowledge-ring node from a live pulse (T-14).
 *
 * No-op (returns false) when: the node already exists on the graph, or the
 * pulse's neuron_type isn't a knowledge-ring member (lesson/memory/knowledge).
 * On success, adds the node at a random position in the KNOWLEDGE_RING band,
 * records it in materializedNodesRef (for rebuildMerge survival across
 * loadGraph() rebuilds), and increments typeCounts[neuron_type].
 */
export function materializeNeuron(
  graph: MultiGraph,
  pulse: Pulse,
  materializedNodesRef: Map<string, KnowledgeNodeAttributes>,
  typeCounts: Map<string, number>,
): boolean {
  if (graph.hasNode(pulse.neuron_id)) return false;
  if (!KNOWLEDGE_RING_TYPES.has(pulse.neuron_type)) return false;

  const { x, y } = randomKnowledgeRingPosition();
  const attrs: KnowledgeNodeAttributes = {
    x,
    y,
    size: 4,
    color: knowledgeRingColor(pulse.neuron_type),
    label: knowledgeRingLabel(pulse.neuron_id),
    type: 'circle',
    neuronType: pulse.neuron_type,
  };

  graph.addNode(pulse.neuron_id, attrs);
  materializedNodesRef.set(pulse.neuron_id, attrs);
  typeCounts.set(pulse.neuron_type, (typeCounts.get(pulse.neuron_type) ?? 0) + 1);
  return true;
}

/**
 * Enforce the per-type LRU budget (T-15). When `typeCounts[neuronType]` exceeds
 * `budget`, drops the node of that type with the smallest `lastPulseRef` value
 * (cold-start nodes default to 0 via seedLastPulse -- they're evicted first).
 *
 * Deletes the evicted id from BOTH the graph AND materializedNodesRef -- doing
 * only one half creates a zombie-node cycle where the evicted id resurrects on
 * the next loadGraph() rebuild via rebuildMerge.
 *
 * Returns the evicted node id, or null if under budget / nothing to evict.
 */
export function evictLru(
  graph: MultiGraph,
  neuronType: string,
  typeCounts: Map<string, number>,
  lastPulseRef: Map<string, number>,
  materializedNodesRef: Map<string, KnowledgeNodeAttributes>,
  budget: number = DEFAULT_TYPE_BUDGET,
): string | null {
  const count = typeCounts.get(neuronType) ?? 0;
  if (count <= budget) return null;

  let evictId: string | null = null;
  let minPulse = Infinity;
  for (const id of graph.nodes()) {
    if (graph.getNodeAttribute(id, 'neuronType') !== neuronType) continue;
    const ts = lastPulseRef.get(id) ?? 0;
    if (ts < minPulse) {
      minPulse = ts;
      evictId = id;
    }
  }
  if (!evictId) return null;

  graph.dropNode(evictId);
  materializedNodesRef.delete(evictId);
  lastPulseRef.delete(evictId);
  typeCounts.set(neuronType, count - 1);
  return evictId;
}

/**
 * Re-merge materialized nodes into a freshly rebuilt graph (T-16).
 *
 * loadGraph() does `new MultiGraph()` (full replace) on every periodic refetch --
 * this survives that by re-adding anything in materializedNodesRef that the
 * cold-start sample didn't already place. The hasNode() guard means a node that
 * landed in BOTH the fresh cold-start sample and materializedNodesRef keeps its
 * cold-start attributes (cold-start wins collisions, never overwritten).
 *
 * After merging, trims each affected type back down to `budget` if the merge
 * pushed it over -- uses lastPulseRef for LRU-consistent eviction (coldest
 * node evicted first), matching the live evictLru path.
 */
export function rebuildMerge(
  graph: MultiGraph,
  materializedNodesRef: Map<string, KnowledgeNodeAttributes>,
  typeCounts: Map<string, number>,
  lastPulseRef: Map<string, number>,
  budget: number = DEFAULT_TYPE_BUDGET,
): void {
  for (const [id, attrs] of materializedNodesRef) {
    if (graph.hasNode(id)) continue;
    graph.addNode(id, attrs);
    typeCounts.set(attrs.neuronType, (typeCounts.get(attrs.neuronType) ?? 0) + 1);
  }

  const types = new Set<string>();
  for (const n of graph.nodes()) {
    const t = graph.getNodeAttribute(n, 'neuronType') as string | undefined;
    if (t) types.add(t);
  }

  for (const t of types) {
    while ((typeCounts.get(t) ?? 0) > budget) {
      let victim: string | null = null;
      let minTs = Infinity;
      for (const n of graph.nodes()) {
        if (graph.getNodeAttribute(n, 'neuronType') !== t) continue;
        const ts = lastPulseRef.get(n) ?? 0;
        if (ts < minTs) { minTs = ts; victim = n; }
      }
      if (!victim) break;
      graph.dropNode(victim);
      materializedNodesRef.delete(victim);
      lastPulseRef.delete(victim);
      typeCounts.set(t, (typeCounts.get(t) ?? 0) - 1);
    }
  }
}

/**
 * Write-if-absent seed for a node's last-pulse timestamp (T-17).
 *
 * Cold-start nodes get seeded at 0 (first eviction candidates) WITHOUT clobbering
 * a timestamp a node earned from an actual pulse before this rebuild ran.
 */
export function seedLastPulse(
  lastPulseRef: Map<string, number>,
  nodeId: string,
  timestamp = 0,
): void {
  if (!lastPulseRef.has(nodeId)) {
    lastPulseRef.set(nodeId, timestamp);
  }
}
