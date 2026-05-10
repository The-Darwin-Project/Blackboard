// BlackBoard/ui/src/components/cortex/CortexGraph.tsx
// @ai-rules:
// 1. [Pattern]: SigmaContainer + useLoadGraph + useRegisterEvents from @react-sigma/core.
// 2. [Pattern]: useWorkerLayoutForceAtlas2 for CONTINUOUS force simulation on knowledge nodes.
// 3. [Constraint]: Executive + event nodes have fixed:true -- FA2 worker ignores them.
// 4. [Gotcha]: FA2 worker runs in background WebWorker. Start on mount, stop on unmount.
// 5. [Pattern]: Structural edges (white, thin) permanent. Activity edges (event-colored) fade over 10s.
// 6. [Pattern]: Force model inspired by update-graph D3 simulation (repulsion + collision + gravity).
import { useEffect, useRef, type FC } from 'react';
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core';
import { useWorkerLayoutForceAtlas2 } from '@react-sigma/layout-forceatlas2';
import Graph from 'graphology';
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
  const base = type === 'agent' ? 6 : type === 'phase' ? 5 : type === 'tool' ? 4 : type === 'event' ? 8 : 3;
  return base + Math.min(heat * 0.2, 6);
}

interface GraphLoaderProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
  activeEvents: ActiveEvent[];
  liveBatches: PulseBatch[];
}

const FA2_SETTINGS = {
  gravity: 0.5,
  scalingRatio: 30,
  strongGravityMode: false,
  barnesHutOptimize: true,
  slowDown: 5,
  edgeWeightInfluence: 0,
};

const GraphLoader: FC<GraphLoaderProps> = ({ neurons, glowingIds, activeEvents, liveBatches }) => {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();
  const graphRef = useRef<Graph | null>(null);
  const activityTimersRef = useRef<Map<string, number>>(new Map());

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
        x = HEMISPHERE_X.knowledge + (Math.random() - 0.5) * 400;
        y = (Math.random() - 0.5) * 500;
      } else if (n.type === 'tool') {
        const group = (n.payload?.group as string) ?? 'observation';
        const groupY = TOOL_GROUP_Y[group] ?? 0;
        x = HEMISPHERE_X.executive + (Math.random() - 0.5) * 60;
        y = groupY + (Math.random() - 0.5) * 20;
      } else if (n.type === 'phase') {
        const phases = ['triage', 'investigate', 'execute', 'verify', 'escalate', 'close'];
        const idx = phases.indexOf(n.payload?.label as string ?? '');
        x = HEMISPHERE_X.executive + 200;
        y = -250 + idx * 100;
      } else {
        const agents = ['architect', 'sysadmin', 'developer', 'qe'];
        const idx = agents.indexOf(n.payload?.label as string ?? '');
        x = HEMISPHERE_X.executive + 350;
        y = -150 + idx * 100;
      }

      graph.addNode(n.id, {
        x, y,
        size: getNeuronSize(n.heat, n.type),
        color: getNeuronColor(n),
        label: (n.payload?.label as string) ?? (n.payload?.title as string) ?? n.id,
        type: 'circle',
        fixed: !isKnowledge,
      });
    }

    // Event hub nodes -- fixed in center column
    for (let i = 0; i < activeEvents.length; i++) {
      const evt = activeEvents[i];
      if (!graph.hasNode(evt.id)) {
        graph.addNode(evt.id, {
          x: HEMISPHERE_X.events + (Math.random() - 0.5) * 30,
          y: i * 80 - (activeEvents.length * 40),
          size: 8,
          color: eventColor(evt.id),
          label: evt.id.slice(0, 12),
          type: 'square',
          fixed: true,
        });
      }
    }

    // Structural edges
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

  useEffect(() => {
    const timers = activityTimersRef.current;
    return () => { for (const t of timers.values()) clearInterval(t); };
  }, []);

  // Node glow + edge opacity reducers
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

const FA2Controller: FC = () => {
  const { start, stop } = useWorkerLayoutForceAtlas2({
    settings: FA2_SETTINGS,
  });

  useEffect(() => {
    start();
    return () => stop();
  }, [start, stop]);

  return null;
};

const DragHandler: FC<{ onClick?: (id: string) => void }> = ({ onClick }) => {
  const registerEvents = useRegisterEvents();
  const sigma = useSigma();
  const dragStateRef = useRef<{ node: string; dragged: boolean } | null>(null);

  useEffect(() => {
    registerEvents({
      downNode: (e) => {
        dragStateRef.current = { node: e.node, dragged: false };
        const graph = sigma.getGraph();
        graph.setNodeAttribute(e.node, 'fixed', true);
        sigma.getCamera().disable();
      },
      mousemove: (e) => {
        if (!dragStateRef.current) return;
        dragStateRef.current.dragged = true;
        const pos = sigma.viewportToGraph(e);
        const graph = sigma.getGraph();
        graph.setNodeAttribute(dragStateRef.current.node, 'x', pos.x);
        graph.setNodeAttribute(dragStateRef.current.node, 'y', pos.y);
      },
      mouseup: () => {
        if (!dragStateRef.current) return;
        const { node, dragged } = dragStateRef.current;
        // If not dragged, treat as click
        if (!dragged && onClick) onClick(node);
        dragStateRef.current = null;
        sigma.getCamera().enable();
      },
    });
  }, [registerEvents, sigma, onClick]);

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
        <FA2Controller />
        <DragHandler onClick={onClickNeuron} />
      </SigmaContainer>
    </div>
  );
}
