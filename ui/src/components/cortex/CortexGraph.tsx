// BlackBoard/ui/src/components/cortex/CortexGraph.tsx
// @ai-rules:
// 1. [Pattern]: SigmaContainer + useLoadGraph + useRegisterEvents from @react-sigma/core.
// 2. [Constraint]: Knowledge neurons positioned left via ForceAtlas2, executive neurons fixed right.
// 3. [Gotcha]: Sigma node reducers run per-frame -- keep isGlowing check cheap (Map lookup).
// 4. [Pattern]: Node click dispatches onSelectNeuron callback for drill-down.
// 5. [Pattern]: Structural edges (white, thin) added at load; activity edges (event-colored) added from liveBatches.
// 6. [Gotcha]: Save executive positions BEFORE ForceAtlas2, restore AFTER -- FA2 moves all nodes.
import { useEffect, useRef, useCallback, type FC } from 'react';
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import { NodeSquareProgram } from '@sigma/node-square';
import '@react-sigma/core/lib/style.css';
import { NEURON_COLORS, AGENT_NEURON_COLORS } from '../../constants/colors';
import {
  getExecutiveNeurons, getStructuralEdges, eventColor,
  HEMISPHERE_X, TOOL_GROUP_Y,
} from './cortex-constants';
import type { ActiveEvent } from '../../api/types';
import type { Neuron, PulseBatch } from './types';

function getNeuronColor(neuron: { type: string; id: string }): string {
  if (neuron.type === 'agent') {
    const name = neuron.id.replace('agent:', '');
    return AGENT_NEURON_COLORS[name] ?? NEURON_COLORS.agent;
  }
  return NEURON_COLORS[neuron.type] ?? '#6b7280';
}

function getNeuronSize(heat: number, type: string): number {
  const base = type === 'agent' ? 12 : type === 'phase' ? 10 : type === 'tool' ? 8 : 3;
  return base + Math.min(heat * 0.3, 12);
}

interface GraphLoaderProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
  activeEvents: ActiveEvent[];
  liveBatches: PulseBatch[];
}

const GraphLoader: FC<GraphLoaderProps> = ({ neurons, glowingIds, activeEvents, liveBatches }) => {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();
  const graphRef = useRef<Graph | null>(null);
  const activityTimersRef = useRef<Map<string, number>>(new Map());

  // Build graph on neuron / activeEvents change
  useEffect(() => {
    const graph = new Graph();
    const executive = getExecutiveNeurons();
    const allNeurons = [...neurons, ...executive];
    const heatMap = new Map(neurons.map(n => [n.id, n.heat]));

    for (const execN of executive) {
      if (heatMap.has(execN.id)) execN.heat = heatMap.get(execN.id)!;
    }

    for (const n of allNeurons) {
      if (graph.hasNode(n.id)) continue;
      const isKnowledge = n.type === 'lesson' || n.type === 'memory';
      let x: number, y: number;

      if (isKnowledge) {
        x = HEMISPHERE_X.knowledge + (Math.random() - 0.5) * 300;
        y = (Math.random() - 0.5) * 400;
      } else if (n.type === 'tool') {
        const group = (n.payload?.group as string) ?? 'observation';
        const groupY = TOOL_GROUP_Y[group] ?? 0;
        x = HEMISPHERE_X.executive + (Math.random() - 0.5) * 80;
        y = groupY + (Math.random() - 0.5) * 30;
      } else if (n.type === 'phase') {
        const phases = ['triage', 'investigate', 'execute', 'verify', 'escalate', 'close'];
        const idx = phases.indexOf(n.payload?.label as string ?? '');
        x = HEMISPHERE_X.executive + 120;
        y = -150 + idx * 60;
      } else {
        const agents = ['architect', 'sysadmin', 'developer', 'qe'];
        const idx = agents.indexOf(n.payload?.label as string ?? '');
        x = HEMISPHERE_X.executive + 200;
        y = -60 + idx * 50;
      }

      graph.addNode(n.id, {
        x, y,
        size: getNeuronSize(n.heat, n.type),
        color: getNeuronColor(n),
        label: (n.payload?.label as string) ?? (n.payload?.title as string) ?? n.id,
        type: 'circle',
      });
    }

    // Save executive positions BEFORE ForceAtlas2
    const savedPositions = new Map<string, { x: number; y: number }>();
    for (const n of allNeurons) {
      if (n.type !== 'lesson' && n.type !== 'memory' && graph.hasNode(n.id)) {
        savedPositions.set(n.id, {
          x: graph.getNodeAttribute(n.id, 'x') as number,
          y: graph.getNodeAttribute(n.id, 'y') as number,
        });
      }
    }

    const knowledgeIds = allNeurons.filter(n => n.type === 'lesson' || n.type === 'memory').map(n => n.id);
    if (knowledgeIds.length > 1) {
      forceAtlas2.assign(graph, {
        iterations: 50,
        settings: {
          gravity: 1,
          scalingRatio: 10,
          barnesHutOptimize: knowledgeIds.length > 50,
        },
      });
    }

    // Restore executive positions AFTER ForceAtlas2
    for (const [id, pos] of savedPositions) {
      if (graph.hasNode(id)) {
        graph.setNodeAttribute(id, 'x', pos.x);
        graph.setNodeAttribute(id, 'y', pos.y);
      }
    }

    // Add event hub nodes (square shape, center position)
    for (let i = 0; i < activeEvents.length; i++) {
      const evt = activeEvents[i];
      if (!graph.hasNode(evt.id)) {
        graph.addNode(evt.id, {
          x: (Math.random() - 0.5) * 50,
          y: i * 80 - (activeEvents.length * 40),
          size: 14,
          color: eventColor(evt.id),
          label: evt.id.slice(0, 12),
          type: 'square',
        });
      }
    }

    // Add structural edges (thin, low opacity, permanent)
    for (const edge of getStructuralEdges()) {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        const edgeId = `struct:${edge.source}:${edge.target}`;
        if (!graph.hasEdge(edgeId)) {
          graph.addEdgeWithKey(edgeId, edge.source, edge.target, {
            color: 'rgba(148, 163, 184, 0.15)',
            size: 0.5,
            structural: true,
          });
        }
      }
    }

    graphRef.current = graph;
    loadGraph(graph);
  }, [neurons, activeEvents, loadGraph]);

  // Activity edges from liveBatches
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    for (const batch of liveBatches) {
      const evtId = batch.event_id;
      if (!graph.hasNode(evtId)) continue;

      for (const pulse of batch.pulses) {
        const edgeId = `activity:${evtId}:${pulse.neuron_id}:${batch.timestamp}`;
        if (graph.hasEdge(edgeId) || !graph.hasNode(pulse.neuron_id)) continue;

        let source = evtId;
        let size = 2;
        let color = eventColor(evtId);

        if (pulse.neuron_type === 'phase') {
          size = 3;
        } else if (pulse.neuron_type === 'lesson' || pulse.neuron_type === 'memory') {
          size = 1;
          // Find last tool in batch to use as source
          const lastTool = [...batch.pulses].reverse().find(p => p.neuron_type === 'tool');
          if (lastTool && graph.hasNode(lastTool.neuron_id)) source = lastTool.neuron_id;
        } else if (pulse.neuron_type === 'agent') {
          source = 'tool:select_agent';
          color = getNeuronColor({ type: 'agent', id: pulse.neuron_id });
          if (!graph.hasNode(source)) continue;
        }

        graph.addEdgeWithKey(edgeId, source, pulse.neuron_id, {
          color,
          size,
          structural: false,
          opacity: 1.0,
        });

        // Schedule fade-out
        const fadeStart = Date.now();
        const timer = window.setInterval(() => {
          if (!graph.hasEdge(edgeId)) { clearInterval(timer); return; }
          const elapsed = (Date.now() - fadeStart) / 1000;
          const opacity = Math.max(0, 1.0 - elapsed / 10);
          if (opacity <= 0) {
            graph.dropEdge(edgeId);
            clearInterval(timer);
            activityTimersRef.current.delete(edgeId);
          } else {
            graph.setEdgeAttribute(edgeId, 'opacity', opacity);
          }
        }, 1000);
        activityTimersRef.current.set(edgeId, timer);
      }
    }

    sigma.refresh();
  }, [liveBatches, sigma]);

  // Cleanup timers on unmount
  useEffect(() => {
    const timers = activityTimersRef.current;
    return () => { for (const t of timers.values()) clearInterval(t); };
  }, []);

  // Glow effect + edge reducer via node/edge reducers
  useEffect(() => {
    if (!sigma.getGraph()) return;

    sigma.setSetting('nodeReducer', (node, data) => {
      const res = { ...data };
      if (glowingIds.has(node)) {
        res.color = '#fbbf24';
        res.size = (data.size ?? 4) * 1.5;
      }
      return res;
    });

    sigma.setSetting('edgeReducer', (_edge, data) => {
      const res = { ...data };
      const opacity = (data as Record<string, unknown>).opacity as number | undefined;
      if (opacity !== undefined && opacity < 1.0) {
        const baseColor = (data.color as string) ?? '#1e293b';
        res.color = baseColor.includes('rgba')
          ? baseColor
          : `${baseColor}${Math.round(opacity * 255).toString(16).padStart(2, '0')}`;
      }
      return res;
    });

    sigma.refresh();
  }, [glowingIds, sigma]);

  return null;
};

const ClickHandler: FC<{ onClick: (id: string) => void }> = ({ onClick }) => {
  const registerEvents = useRegisterEvents();
  const cb = useCallback(
    (event: { node: string }) => onClick(event.node),
    [onClick],
  );
  useEffect(() => { registerEvents({ clickNode: cb }); }, [registerEvents, cb]);
  return null;
};

interface CortexGraphProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
  activeEvents?: ActiveEvent[];
  liveBatches?: PulseBatch[];
  dimmedIds?: Set<string>;
  onClickNeuron?: (id: string) => void;
  className?: string;
}

export default function CortexGraph({
  neurons, glowingIds, activeEvents = [], liveBatches = [],
  dimmedIds, onClickNeuron, className,
}: CortexGraphProps) {
  return (
    <div className={`relative ${className ?? ''}`}>
      <SigmaContainer
        style={{ width: '100%', height: '100%', background: '#030712' }}
        settings={{
          defaultNodeColor: '#475569',
          defaultEdgeColor: '#1e293b',
          labelColor: { color: '#94a3b8' },
          labelFont: 'Inter, system-ui, sans-serif',
          labelSize: 10,
          labelRenderedSizeThreshold: 4,
          renderLabels: true,
          enableEdgeEvents: false,
          nodeProgramClasses: { square: NodeSquareProgram },
          ...(dimmedIds ? {
            nodeReducer: (node: string, data: Record<string, unknown>) => {
              if (dimmedIds.has(node)) return { ...data, color: '#1e293b', size: 2, label: '' };
              return data;
            },
          } : {}),
        }}
      >
        <GraphLoader
          neurons={neurons}
          glowingIds={glowingIds}
          activeEvents={activeEvents}
          liveBatches={liveBatches}
        />
        {onClickNeuron && <ClickHandler onClick={onClickNeuron} />}
      </SigmaContainer>
    </div>
  );
}
