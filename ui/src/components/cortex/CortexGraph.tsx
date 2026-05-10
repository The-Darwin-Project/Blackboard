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
import '@react-sigma/core/lib/style.css';
import { NEURON_COLORS, AGENT_NEURON_COLORS } from '../../constants/colors';
import {
  getExecutiveNeurons, getStructuralEdges, eventColor,
  HEMISPHERE_X, TOOL_GROUP_Y,
} from './cortex-constants';
import type { ActiveEvent } from '../../api/types';
import type { Neuron, PulseBatch } from './types';
import BrainCore from './BrainCore';

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
  gravity: 0.3,
  scalingRatio: 50,
  strongGravityMode: false,
  barnesHutOptimize: true,
  slowDown: 30,
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

    for (const n of allNeurons) {
      if (graph.hasNode(n.id)) continue;
      const isKnowledge = n.type === 'lesson' || n.type === 'memory';
      let x: number, y: number;

      if (isKnowledge) {
        // Spawn in a ring around the center, keeping distance from the core
        const angle = Math.random() * Math.PI * 2;
        const minRadius = 200;
        const maxRadius = 500;
        const radius = minRadius + Math.random() * (maxRadius - minRadius);
        x = radius * Math.cos(angle);
        y = radius * Math.sin(angle);
      } else if (n.type === 'tool') {
        const group = (n.payload?.group as string) ?? 'observation';
        const groupTools = Object.entries(TOOL_GROUP_Y).find(([g]) => g === group);
        const groupY = groupTools ? groupTools[1] : 0;
        const toolsInGroup = allNeurons.filter(
          t => t.type === 'tool' && (t.payload?.group as string) === group
        );
        const toolIdx = toolsInGroup.indexOf(n);
        x = HEMISPHERE_X.executive + toolIdx * 50;
        y = groupY;
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

      let label = '';
      if (n.type === 'memory') {
        const symptom = n.payload?.symptom as string;
        const service = n.payload?.service as string;
        label = symptom ? symptom.slice(0, 30) : service ? service : n.id.slice(0, 12);
      } else {
        label = (n.payload?.label as string) ?? (n.payload?.title as string) ?? n.id.slice(0, 15);
      }

      graph.addNode(n.id, {
        x, y,
        size: getNeuronSize(n.heat, n.type),
        color: getNeuronColor(n),
        label,
        type: 'circle',
      });
    }

    // Event hub nodes -- orbit around the knowledge cluster perimeter
    const eventCount = activeEvents.length;
    for (let i = 0; i < eventCount; i++) {
      const evt = activeEvents[i];
      if (!graph.hasNode(evt.id)) {
        const angle = (i / Math.max(eventCount, 1)) * 2 * Math.PI - Math.PI / 2;
        const orbitRadius = 350;
        graph.addNode(evt.id, {
          x: HEMISPHERE_X.knowledge + orbitRadius * Math.cos(angle),
          y: orbitRadius * Math.sin(angle),
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

  // Activity edges from liveBatches
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    for (const batch of liveBatches) {
      const evtId = batch.event_id;
      if (!evtId) continue;

      // Dynamically add event node if it arrived via pulse but isn't in activeEvents yet
      if (!graph.hasNode(evtId)) {
        const existingEvents = graph.nodes().filter((n: string) => {
          try { return graph.getNodeAttribute(n, 'type') === 'square'; } catch { return false; }
        });
        graph.addNode(evtId, {
          x: HEMISPHERE_X.knowledge + 350 * Math.cos(existingEvents.length * 1.5),
          y: 350 * Math.sin(existingEvents.length * 1.5),
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
          opacity: 1.0,
        });
        sigma.refresh();

        // 5s solid at full opacity, then 5s fade (0.1 every 0.5s)
        const createdAt = Date.now();
        const timer = window.setInterval(() => {
          if (!graph.hasEdge(edgeId)) { clearInterval(timer); return; }
          const elapsed = (Date.now() - createdAt) / 1000;
          if (elapsed < 5) return; // hold solid for 5s
          const fadeElapsed = elapsed - 5;
          const linearOpacity = Math.max(0, 1.0 - fadeElapsed / 5);
          const opacity = linearOpacity * linearOpacity; // quadratic ease-out: visible longer, then vanishes
          if (opacity <= 0) {
            graph.dropEdge(edgeId);
            clearInterval(timer);
            activityTimersRef.current.delete(edgeId);
          } else {
            graph.setEdgeAttribute(edgeId, 'opacity', opacity);
          }
        }, 500);
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
    <div className={`relative ${className ?? ''}`} style={{ background: '#030712' }}>
      <BrainCore />
      <SigmaContainer
        style={{ width: '100%', height: '100%', background: 'transparent', position: 'relative', zIndex: 1 }}
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
