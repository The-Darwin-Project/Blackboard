// BlackBoard/ui/src/components/cortex/cortex-pulse-handler.test.ts
// @ai-rules:
// 1. [Pattern]: Written from the knowledge-scroll plan's Test Specification (T-14..T-17) BEFORE
//    `cortex-pulse-handler.ts` exists -- import will fail until the executor extracts these pure
//    functions out of CortexGraph.tsx's inline pulse-handling effect (Step 6b/6c/6d of the plan).
// 2. [Assumption]: The extracted module exports four pure functions operating on a plain
//    graphology `MultiGraph` + plain `Map` instances (NOT React refs -- refs are unwrapped to
//    their `.current` Map by the caller before invoking these functions):
//      - materializeNeuron(graph, pulse, materializedNodesRef, typeCounts): boolean
//      - evictLru(graph, neuronType, typeCounts, lastPulseRef, materializedNodesRef, budget?): string | null
//      - rebuildMerge(graph, materializedNodesRef, typeCounts, budget?): void
//      - seedLastPulse(lastPulseRef, nodeId, timestamp?): void
//    Also assumes exported constants `KNOWLEDGE_RING = { min: 560, max: 720 }` and a default
//    per-type budget of 600 (overridable via the `budget` param for fast, focused tests).
//    If the executor's actual signatures differ (e.g. a single options-object param, or
//    eviction folded into materializeNeuron itself), this file's assertions on call shape will
//    fail first and cleanly -- that mismatch is the intended reconciliation signal, not a bug
//    in either artifact.
// 3. [Constraint]: Radius checks use `Math.sqrt(x**2 + y**2)` against the RING band from the
//    plan (560-720) rather than snapshotting exact x/y, since placement angle is randomized.
import { describe, expect, it } from 'vitest';
import { MultiGraph } from 'graphology';
import {
  materializeNeuron,
  evictLru,
  rebuildMerge,
  seedLastPulse,
  KNOWLEDGE_RING,
  type KnowledgeNodeAttributes,
} from './cortex-pulse-handler';
import type { Pulse } from './types';

const RING_MIN = KNOWLEDGE_RING?.min ?? 560;
const RING_MAX = KNOWLEDGE_RING?.max ?? 720;

function radiusOf(attrs: { x: number; y: number }): number {
  return Math.sqrt(attrs.x ** 2 + attrs.y ** 2);
}

function makePulse(overrides: Partial<Pulse> = {}): Pulse {
  return {
    neuron_id: 'knowledge:fact-abc',
    neuron_type: 'knowledge',
    score: 0.5,
    injected: false,
    ...overrides,
  };
}

// =========================================================================
// T-14: Pulse materialize adds missing node
// =========================================================================

describe('materializeNeuron (T-14)', () => {
  it('adds a missing knowledge-ring node with neuronType attr inside the 560-720 radius band', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const typeCounts = new Map<string, number>();
    const pulse = makePulse({ neuron_id: 'knowledge:fact-1', neuron_type: 'knowledge' });

    const added = materializeNeuron(graph, pulse, materializedNodesRef, typeCounts);

    expect(added).toBe(true);
    expect(graph.hasNode('knowledge:fact-1')).toBe(true);
    const attrs = graph.getNodeAttributes('knowledge:fact-1');
    expect(attrs.neuronType).toBe('knowledge');
    const radius = radiusOf(attrs as { x: number; y: number });
    expect(radius).toBeGreaterThanOrEqual(RING_MIN);
    expect(radius).toBeLessThanOrEqual(RING_MAX);
  });

  it('updates materializedNodesRef and typeCounts as a side effect', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const typeCounts = new Map<string, number>();
    const pulse = makePulse({ neuron_id: 'lesson:l-1', neuron_type: 'lesson' });

    materializeNeuron(graph, pulse, materializedNodesRef, typeCounts);

    expect(materializedNodesRef.has('lesson:l-1')).toBe(true);
    expect(materializedNodesRef.get('lesson:l-1')?.neuronType).toBe('lesson');
    expect(typeCounts.get('lesson')).toBe(1);
  });

  it.each(['lesson', 'memory', 'knowledge'] as const)(
    'accepts %s as a knowledge-ring neuron type',
    (neuronType) => {
      const graph = new MultiGraph();
      const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
      const typeCounts = new Map<string, number>();
      const pulse = makePulse({ neuron_id: `${neuronType}:x-1`, neuron_type: neuronType });

      const added = materializeNeuron(graph, pulse, materializedNodesRef, typeCounts);

      expect(added).toBe(true);
      expect(graph.hasNode(`${neuronType}:x-1`)).toBe(true);
    },
  );

  it('does not materialize non-knowledge-ring neuron types (e.g. tool/phase/agent)', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const typeCounts = new Map<string, number>();
    const pulse = makePulse({ neuron_id: 'tool:select_agent', neuron_type: 'tool' });

    const added = materializeNeuron(graph, pulse, materializedNodesRef, typeCounts);

    expect(added).toBe(false);
    expect(graph.hasNode('tool:select_agent')).toBe(false);
    expect(materializedNodesRef.has('tool:select_agent')).toBe(false);
    expect(typeCounts.get('tool')).toBeFalsy();
  });

  it('is a no-op when the node already exists on the graph', () => {
    const graph = new MultiGraph();
    graph.addNode('knowledge:already-there', {
      x: 600, y: 0, size: 4, color: '#06b6d4', label: 'x', type: 'circle', neuronType: 'knowledge',
    });
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const typeCounts = new Map<string, number>([['knowledge', 1]]);
    const pulse = makePulse({ neuron_id: 'knowledge:already-there', neuron_type: 'knowledge' });

    const added = materializeNeuron(graph, pulse, materializedNodesRef, typeCounts);

    expect(added).toBe(false);
    expect(typeCounts.get('knowledge')).toBe(1); // unchanged, not double-counted
  });
});

// =========================================================================
// T-15: LRU eviction at budget
// =========================================================================

describe('evictLru (T-15)', () => {
  function seedNodes(
    graph: MultiGraph,
    materializedNodesRef: Map<string, KnowledgeNodeAttributes>,
    lastPulseRef: Map<string, number>,
    count: number,
    neuronType = 'knowledge',
  ) {
    for (let i = 0; i < count; i++) {
      const id = `${neuronType}:node-${i}`;
      const attrs: KnowledgeNodeAttributes = {
        x: 600, y: 0, size: 4, color: '#06b6d4', label: id, type: 'circle', neuronType,
      };
      graph.addNode(id, attrs);
      materializedNodesRef.set(id, attrs);
      lastPulseRef.set(id, i); // node-0 has the oldest (smallest) timestamp
    }
  }

  it('does nothing when the type is under budget', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const lastPulseRef = new Map<string, number>();
    const typeCounts = new Map<string, number>();
    seedNodes(graph, materializedNodesRef, lastPulseRef, 3);
    typeCounts.set('knowledge', 3);

    const evicted = evictLru(graph, 'knowledge', typeCounts, lastPulseRef, materializedNodesRef, 3);

    expect(evicted).toBeNull();
    expect(graph.order).toBe(3);
    expect(typeCounts.get('knowledge')).toBe(3);
  });

  it('evicts the oldest-unseen node (min lastPulseRef) when a type exceeds budget', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const lastPulseRef = new Map<string, number>();
    const typeCounts = new Map<string, number>();
    seedNodes(graph, materializedNodesRef, lastPulseRef, 4); // node-0..node-3, node-0 is oldest
    typeCounts.set('knowledge', 4);

    const evicted = evictLru(graph, 'knowledge', typeCounts, lastPulseRef, materializedNodesRef, 3);

    expect(evicted).toBe('knowledge:node-0');
    expect(graph.hasNode('knowledge:node-0')).toBe(false);
    expect(materializedNodesRef.has('knowledge:node-0')).toBe(false);
    expect(typeCounts.get('knowledge')).toBe(3);
    // Survivors remain untouched
    expect(graph.hasNode('knowledge:node-1')).toBe(true);
    expect(graph.hasNode('knowledge:node-3')).toBe(true);
  });

  it('only evicts nodes of the matching neuronType, ignoring cheaper-timestamp nodes of other types', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const lastPulseRef = new Map<string, number>();
    const typeCounts = new Map<string, number>();

    // A "memory" node with an older timestamp than any "knowledge" node must NOT be evicted
    // when we ask evictLru to enforce the "knowledge" budget.
    seedNodes(graph, materializedNodesRef, lastPulseRef, 1, 'memory');
    lastPulseRef.set('memory:node-0', -100); // artificially the oldest of all
    typeCounts.set('memory', 1);

    seedNodes(graph, materializedNodesRef, lastPulseRef, 4, 'knowledge');
    typeCounts.set('knowledge', 4);

    const evicted = evictLru(graph, 'knowledge', typeCounts, lastPulseRef, materializedNodesRef, 3);

    expect(evicted).toBe('knowledge:node-0');
    expect(graph.hasNode('memory:node-0')).toBe(true); // untouched
    expect(typeCounts.get('memory')).toBe(1);
  });

  it('enforces the literal 600/type budget (601st node triggers eviction) using the default budget', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const lastPulseRef = new Map<string, number>();
    const typeCounts = new Map<string, number>();
    seedNodes(graph, materializedNodesRef, lastPulseRef, 601, 'knowledge');
    typeCounts.set('knowledge', 601);

    // No explicit budget arg -- rely on the documented default of 600.
    const evicted = evictLru(graph, 'knowledge', typeCounts, lastPulseRef, materializedNodesRef);

    expect(evicted).toBe('knowledge:node-0');
    expect(graph.order).toBe(600);
    expect(typeCounts.get('knowledge')).toBe(600);
  });
});

// =========================================================================
// T-16: Cold-start rebuild preserves materialized nodes
// =========================================================================

describe('rebuildMerge (T-16)', () => {
  it('re-adds materializedNodesRef entries missing from a freshly rebuilt graph', () => {
    const graph = new MultiGraph(); // simulates loadGraph()'s `new MultiGraph()` full replace
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>([
      ['knowledge:pulsed-1', { x: 600, y: 100, size: 4, color: '#06b6d4', label: 'a', type: 'circle', neuronType: 'knowledge' }],
      ['lesson:pulsed-2', { x: -600, y: 50, size: 4, color: '#22c55e', label: 'b', type: 'circle', neuronType: 'lesson' }],
    ]);
    const typeCounts = new Map<string, number>();

    rebuildMerge(graph, materializedNodesRef, typeCounts, new Map());

    expect(graph.hasNode('knowledge:pulsed-1')).toBe(true);
    expect(graph.hasNode('lesson:pulsed-2')).toBe(true);
    expect(graph.getNodeAttribute('knowledge:pulsed-1', 'neuronType')).toBe('knowledge');
  });

  it('does not overwrite a node that already landed in the cold-start sample (hasNode guard)', () => {
    const graph = new MultiGraph();
    const coldStartAttrs: KnowledgeNodeAttributes = {
      x: 601, y: 601, size: 3, color: '#06b6d4', label: 'cold-start-version', type: 'circle', neuronType: 'knowledge',
    };
    graph.addNode('knowledge:collides', coldStartAttrs);

    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>([
      ['knowledge:collides', { x: 1, y: 1, size: 99, color: '#000000', label: 'materialized-version', type: 'circle', neuronType: 'knowledge' }],
    ]);
    const typeCounts = new Map<string, number>([['knowledge', 1]]);

    rebuildMerge(graph, materializedNodesRef, typeCounts, new Map());

    // Cold-start version must win -- rebuildMerge must guard with graph.hasNode() before adding.
    expect(graph.getNodeAttribute('knowledge:collides', 'label')).toBe('cold-start-version');
  });

  it('enforces the per-type budget after merging materialized nodes back in', () => {
    const graph = new MultiGraph();
    const materializedNodesRef = new Map<string, KnowledgeNodeAttributes>();
    const typeCounts = new Map<string, number>();
    for (let i = 0; i < 5; i++) {
      const id = `knowledge:extra-${i}`;
      const attrs: KnowledgeNodeAttributes = {
        x: 600, y: 0, size: 4, color: '#06b6d4', label: id, type: 'circle', neuronType: 'knowledge',
      };
      materializedNodesRef.set(id, attrs);
    }

    rebuildMerge(graph, materializedNodesRef, typeCounts, new Map(), 3);

    const knowledgeNodeCount = graph.nodes().filter(
      (n) => graph.getNodeAttribute(n, 'neuronType') === 'knowledge',
    ).length;
    expect(knowledgeNodeCount).toBeLessThanOrEqual(3);
  });
});

// =========================================================================
// T-17: Cold-start seeds lastPulseRef write-if-absent
// =========================================================================

describe('seedLastPulse (T-17)', () => {
  it('seeds a cold-start node at 0 when absent from lastPulseRef', () => {
    const lastPulseRef = new Map<string, number>();

    seedLastPulse(lastPulseRef, 'knowledge:cold-1');

    expect(lastPulseRef.get('knowledge:cold-1')).toBe(0);
  });

  it('does not overwrite an existing (pulsed) timestamp -- write-if-absent semantics', () => {
    const lastPulseRef = new Map<string, number>([['knowledge:pulsed-1', 1_726_000_000_000]]);

    seedLastPulse(lastPulseRef, 'knowledge:pulsed-1');

    expect(lastPulseRef.get('knowledge:pulsed-1')).toBe(1_726_000_000_000);
  });

  it('on rebuild, pulsed nodes keep their timestamp while cold-start-only nodes get 0', () => {
    const lastPulseRef = new Map<string, number>([['knowledge:pulsed-during-session', 42]]);
    const coldStartIds = ['knowledge:pulsed-during-session', 'knowledge:never-pulsed'];

    for (const id of coldStartIds) {
      seedLastPulse(lastPulseRef, id);
    }

    expect(lastPulseRef.get('knowledge:pulsed-during-session')).toBe(42);
    expect(lastPulseRef.get('knowledge:never-pulsed')).toBe(0);
  });
});
