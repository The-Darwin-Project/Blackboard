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
import { MultiGraph } from 'graphology';
import { NodeSquareProgram } from '@sigma/node-square';
import { NodeCircleProgram } from 'sigma/rendering';
import '@react-sigma/core/lib/style.css';
import { NEURON_COLORS, AGENT_NEURON_COLORS } from '../../constants/colors';
import {
  getExecutiveNeurons, getStructuralEdges, eventColor,
} from './cortex-constants';
import type { ActiveEvent } from '../../api/types';
import type { Neuron, PulseBatch } from './types';
// import BrainCore from './BrainCore'; // disabled -- needs its own dedicated view

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
  gravity: 1,
  scalingRatio: 10,
  strongGravityMode: false,
  barnesHutOptimize: true,
  slowDown: 100,
  edgeWeightInfluence: 1,
  linLogMode: true,
};

const GraphLoader: FC<GraphLoaderProps> = ({ neurons, glowingIds, activeEvents, liveBatches }) => {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();
  const graphRef = useRef<MultiGraph | null>(null);
  const activityTimersRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const graph = new MultiGraph();
    const executive = getExecutiveNeurons();
    const allNeurons = [...neurons, ...executive];
    const heatMap = new Map(neurons.map(n => [n.id, n.heat]));

    for (const execN of executive) {
      if (heatMap.has(execN.id)) execN.heat = heatMap.get(execN.id)!;
    }

    // Concentric ring layout: brain core -> executive (ring 1) -> knowledge (ring 2) -> events (ring 3)
    const RING = { executive: 250, knowledge: { min: 400, max: 650 }, events: 800 };

    // Count executive nodes for even distribution
    const toolNodes = allNeurons.filter(n => n.type === 'tool');
    const phaseNodes = allNeurons.filter(n => n.type === 'phase');
    const agentNodes = allNeurons.filter(n => n.type === 'agent');
    const execTotal = toolNodes.length + phaseNodes.length + agentNodes.length;
    let execIdx = 0;

    for (const n of allNeurons) {
      if (graph.hasNode(n.id)) continue;
      const isKnowledge = n.type === 'lesson' || n.type === 'memory';
      let x: number, y: number;

      if (isKnowledge) {
        // Ring 2: knowledge nodes in a ring around executive core
        const angle = Math.random() * Math.PI * 2;
        const radius = RING.knowledge.min + Math.random() * (RING.knowledge.max - RING.knowledge.min);
        x = radius * Math.cos(angle);
        y = radius * Math.sin(angle);
      } else {
        // Ring 1: executive nodes distributed evenly around inner ring
        const angle = (execIdx / Math.max(execTotal, 1)) * 2 * Math.PI - Math.PI / 2;
        x = RING.executive * Math.cos(angle);
        y = RING.executive * Math.sin(angle);
        execIdx++;
      }

      let label = '';
      if (n.type === 'memory') {
        const symptom = n.payload?.symptom as string;
        const service = n.payload?.service as string;
        label = symptom ? symptom.slice(0, 30) : service ? service : n.id.slice(0, 12);
      } else {
        label = (n.payload?.label as string) ?? (n.payload?.title as string) ?? n.id.slice(0, 15);
      }

      const isExecutive = n.type === 'tool' || n.type === 'phase' || n.type === 'agent';
      graph.addNode(n.id, {
        x, y,
        size: getNeuronSize(n.heat, n.type),
        color: getNeuronColor(n),
        label,
        type: 'circle',
        fixed: isExecutive,
      });
    }

    // Ring 3: Event nodes on the outermost ring
    const eventCount = activeEvents.length;
    for (let i = 0; i < eventCount; i++) {
      const evt = activeEvents[i];
      if (!graph.hasNode(evt.id)) {
        const angle = (i / Math.max(eventCount, 1)) * 2 * Math.PI - Math.PI / 2;
        graph.addNode(evt.id, {
          x: RING.events * Math.cos(angle),
          y: RING.events * Math.sin(angle),
          size: 8,
          color: eventColor(evt.id),
          label: evt.id.slice(0, 12),
          type: 'square',
        });
      }
    }

    // Structural edges
    for (const edge of getStructuralEdges()) {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        const edgeId = `struct:${edge.source}:${edge.target}`;
        if (!graph.hasEdge(edgeId)) {
          graph.addEdgeWithKey(edgeId, edge.source, edge.target, {
            color: '#334155',
            size: 1,
            structural: true,
          });
        }
      }
    }

    graphRef.current = graph;
    loadGraph(graph);
  }, [neurons, activeEvents, loadGraph]);

  // Activity edges from liveBatches -- mutate Sigma's LIVE graph directly
  useEffect(() => {
    const graph = sigma.getGraph();
    if (!graph || graph.order === 0) return;

    for (const batch of liveBatches) {
      const evtId = batch.event_id;
      if (!evtId) continue;

      // Dynamically add event node if needed
      if (!graph.hasNode(evtId)) {
        const evtCount = graph.nodes().filter((n: string) => {
          try { return graph.getNodeAttribute(n, 'type') === 'square'; } catch { return false; }
        }).length;
        graph.addNode(evtId, {
          x: 600 * Math.cos(evtCount * 1.5),
          y: 600 * Math.sin(evtCount * 1.5),
          size: 8,
          color: eventColor(evtId),
          label: evtId.slice(0, 12),
          type: 'square',
        });
      }

      for (const pulse of batch.pulses) {
        const edgeId = `activity:${evtId}:${pulse.neuron_id}:${batch.timestamp}`;
        if (graph.hasEdge(edgeId) || !graph.hasNode(pulse.neuron_id)) continue;

        let source = evtId;
        let size = 4;
        let color = eventColor(evtId);

        if (pulse.neuron_type === 'phase') {
          size = 6;
        } else if (pulse.neuron_type === 'lesson' || pulse.neuron_type === 'memory') {
          size = 2;
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
        });

        // 5s solid, then 5s fade
        const createdAt = Date.now();
        const timer = window.setInterval(() => {
          if (!graph.hasEdge(edgeId)) { clearInterval(timer); return; }
          const elapsed = (Date.now() - createdAt) / 1000;
          if (elapsed < 5) return;
          const fadeElapsed = elapsed - 5;
          const linearOpacity = Math.max(0, 1.0 - fadeElapsed / 5);
          const opacity = linearOpacity * linearOpacity;
          if (opacity <= 0) {
            graph.dropEdge(edgeId);
            clearInterval(timer);
            activityTimersRef.current.delete(edgeId);
          } else {
            graph.setEdgeAttribute(edgeId, 'size', Math.max(0.5, size * opacity));
          }
        }, 500);
        activityTimersRef.current.set(edgeId, timer);
      }
    }
  }, [liveBatches, sigma]); // eslint-disable-line react-hooks/exhaustive-deps

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
        res.size = (data.size ?? 4) * 1.8;
      }
      return res;
    });

    sigma.setSetting('edgeReducer', (_edge, data) => {
      const res = { ...data };
      const opacity = (data as Record<string, unknown>).opacity as number | undefined;
      if (opacity !== undefined && opacity < 1.0) {
        // Sigma v3 WebGL can't reliably parse #RRGGBBAA.
        // Fade via size reduction + color dimming toward background.
        res.size = Math.max(0.5, ((data.size as number) ?? 2) * opacity);
        // Blend color toward background (#030712) based on opacity
        const base = data.color as string ?? '#1e293b';
        if (base.startsWith('#') && base.length === 7) {
          const r = parseInt(base.slice(1, 3), 16);
          const g = parseInt(base.slice(3, 5), 16);
          const b = parseInt(base.slice(5, 7), 16);
          const br = 3, bg = 7, bb = 18; // #030712 background
          const mr = Math.round(r * opacity + br * (1 - opacity));
          const mg = Math.round(g * opacity + bg * (1 - opacity));
          const mb = Math.round(b * opacity + bb * (1 - opacity));
          res.color = `#${mr.toString(16).padStart(2,'0')}${mg.toString(16).padStart(2,'0')}${mb.toString(16).padStart(2,'0')}`;
        }
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
  const dragStateRef = useRef<{ node: string; dragged: boolean; wasFixed: boolean } | null>(null);

  useEffect(() => {
    registerEvents({
      downNode: (e) => {
        const graph = sigma.getGraph();
        const wasFixed = graph.getNodeAttribute(e.node, 'fixed') as boolean ?? false;
        dragStateRef.current = { node: e.node, dragged: false, wasFixed };
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
        const { node, dragged, wasFixed } = dragStateRef.current;
        const graph = sigma.getGraph();
        // Restore original fixed state -- knowledge nodes go back to unfixed
        // so FA2 worker pulls connected nodes toward new position
        graph.setNodeAttribute(node, 'fixed', wasFixed);
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
    <div className={`relative ${className ?? ''}`} style={{ background: '#030712', width: '100%', height: '100%' }}>
      <SigmaContainer
        style={{ width: '100%', height: '100%', background: 'transparent' }}
        settings={{
          defaultNodeColor: '#475569',
          defaultEdgeColor: '#1e293b',
          labelColor: { color: '#94a3b8' },
          labelFont: 'Inter, system-ui, sans-serif',
          labelSize: 10,
          labelRenderedSizeThreshold: 4,
          renderLabels: true,
          enableEdgeEvents: false,
          stagePadding: 0,
          nodeProgramClasses: {
            circle: NodeCircleProgram,
            square: NodeSquareProgram,
          },
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
