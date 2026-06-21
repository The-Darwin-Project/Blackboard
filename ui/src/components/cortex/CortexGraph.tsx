// BlackBoard/ui/src/components/cortex/CortexGraph.tsx
// @ai-rules:
// 1. [Pattern]: SigmaContainer + useLoadGraph + useRegisterEvents from @react-sigma/core.
// 2. [Pattern]: useWorkerLayoutForceAtlas2 for CONTINUOUS force simulation on knowledge nodes.
// 3. [Constraint]: Executive + skill + event nodes have fixed:true -- FA2 worker ignores them.
// 4. [Gotcha]: FA2 worker runs in background WebWorker. Start on mount, stop on unmount.
// 5. [Pattern]: Structural edges (white, thin) permanent. Activity edges (event-colored) fade over 10s.
// 6. [Pattern]: Force model inspired by update-graph D3 simulation (repulsion + collision + gravity).
// 7. [Pattern]: Ring layout: executive (r=250, fixed), skills (r=320, fixed), knowledge (r=400-650, FA2-free), events (r=800, fixed).
// 8. [Gotcha]: Skill node color resolved INLINE during creation (SKILL_TAG_COLORS[tag_type]). getNeuronColor() has no payload access.
// 9. [Pattern]: Ripple overlay via DOM: sigma.getContainer().appendChild(div.skill-ripple). activeRipplesRef cap=10. idempotent cleanup via `cleaned` flag.
import { useEffect, useRef, type FC } from 'react';
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core';
import { useWorkerLayoutForceAtlas2 } from '@react-sigma/layout-forceatlas2';
import { MultiGraph } from 'graphology';
import { NodeSquareProgram } from '@sigma/node-square';
import { NodeCircleProgram } from 'sigma/rendering';
import '@react-sigma/core/lib/style.css';
import { NEURON_COLORS, AGENT_NEURON_COLORS, DOMAIN_NEURON_COLORS, SKILL_TAG_COLORS } from '../../constants/colors';
import {
  getExecutiveNeurons, getStructuralEdges, eventColor, PHASE_SKILL_FOLDERS,
} from './cortex-constants';
import type { ActiveEvent } from '../../api/types';
import type { Neuron, PulseBatch } from './types';
// import BrainCore from './BrainCore'; // disabled -- needs its own dedicated view

function getNeuronColor(neuron: { type: string; id: string }): string {
  if (neuron.type === 'agent') {
    const name = neuron.id.replace('agent:', '');
    return AGENT_NEURON_COLORS[name] ?? NEURON_COLORS.agent;
  }
  if (neuron.type === 'domain') {
    const name = neuron.id.replace('domain:', '');
    return DOMAIN_NEURON_COLORS[name] ?? NEURON_COLORS.domain;
  }
  return NEURON_COLORS[neuron.type] ?? '#6b7280';
}

function getNeuronSize(heat: number, type: string): number {
  const base = type === 'agent' ? 6 : type === 'phase' ? 5 : type === 'domain' ? 5
    : type === 'tool' ? 4 : type === 'event' ? 8 : type === 'skill' ? 3 : 3;
  const maxGrowth = type === 'skill' ? 2 : 4;
  // Logarithmic scaling: heat=1→+0.7, heat=10→+2.3, heat=50→+3.9, heat=100→+4 (capped)
  const growth = heat > 0 ? Math.min(Math.log(heat + 1) * 1.0, maxGrowth) : 0;
  return base + growth;
}

interface GraphLoaderProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
  activeEvents: ActiveEvent[];
  liveBatches: PulseBatch[];
  dimmedIds?: Set<string>;
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

const GraphLoader: FC<GraphLoaderProps> = ({ neurons, glowingIds, activeEvents, liveBatches, dimmedIds }) => {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();
  const activityTimersRef = useRef<Map<string, number>>(new Map());
  const processedBatchesRef = useRef<Set<string>>(new Set());
  const activeRipplesRef = useRef(0);
  const lastPulseRef = useRef<Map<string, number>>(new Map());
  const baseSizeRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    processedBatchesRef.current.clear();
    baseSizeRef.current.clear();
    const graph = new MultiGraph();
    const executive = getExecutiveNeurons();
    const allNeurons = [...neurons, ...executive];
    const heatMap = new Map(neurons.map(n => [n.id, n.heat]));

    for (const execN of executive) {
      if (heatMap.has(execN.id)) execN.heat = heatMap.get(execN.id)!;
    }

    // Concentric ring layout: brain core -> executive (ring 1) -> skills (ring 2) -> knowledge (ring 3) -> events (ring 4)
    const RING = { executive: 280, skills: 460, knowledge: { min: 560, max: 720 }, events: 880 };

    // Count executive and skill nodes for even distribution
    const toolNodes = allNeurons.filter(n => n.type === 'tool');
    const phaseNodes = allNeurons.filter(n => n.type === 'phase');
    const agentNodes = allNeurons.filter(n => n.type === 'agent');
    const domainNodes = allNeurons.filter(n => n.type === 'domain');
    const skillNodes = allNeurons.filter(n => n.type === 'skill');
    const execTotal = toolNodes.length + phaseNodes.length + agentNodes.length + domainNodes.length;
    let execIdx = 0;
    let skillIdx = 0;

    for (const n of allNeurons) {
      if (graph.hasNode(n.id)) continue;
      const isKnowledge = n.type === 'lesson' || n.type === 'memory' || n.type === 'knowledge';
      let x: number, y: number;

      if (n.type === 'skill') {
        // Ring 2: skill nodes on fixed ring between executive and knowledge
        const angle = (skillIdx / Math.max(skillNodes.length, 1)) * 2 * Math.PI - Math.PI / 2;
        x = RING.skills * Math.cos(angle);
        y = RING.skills * Math.sin(angle);
        skillIdx++;
      } else if (isKnowledge) {
        // Ring 3: knowledge nodes in randomized band around skill ring
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
      } else if (n.type === 'knowledge') {
        const topic = n.payload?.topic as string;
        const scope = n.payload?.scope as string;
        label = topic ? `${topic.slice(0, 25)} [${scope}]` : n.id.slice(0, 12);
      } else {
        label = (n.payload?.label as string) ?? (n.payload?.title as string) ?? n.id.slice(0, 15);
      }

      const isExecutive = n.type === 'tool' || n.type === 'phase' || n.type === 'agent' || n.type === 'domain';
      const isFixed = isExecutive || n.type === 'skill';
      // Skill color resolved inline (tag_type in payload, not available in getNeuronColor signature)
      let nodeColor = n.type === 'skill'
        ? (SKILL_TAG_COLORS[(n.payload as { tag_type?: string })?.tag_type ?? ''] ?? NEURON_COLORS.skill)
        : getNeuronColor(n);
      // Dim cold skills (heat=0) to 40% opacity
      if (n.type === 'skill' && n.heat === 0) {
        nodeColor = nodeColor + '66'; // hex alpha ~40%
      }
      graph.addNode(n.id, {
        x, y,
        size: getNeuronSize(n.heat, n.type),
        color: nodeColor,
        label: n.type === 'skill' ? '' : label,
        type: 'circle',
        fixed: isFixed,
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

    // Structural edges (executive hemisphere chains)
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

    // Dynamic phase→skill structural edges (always/ skills are omnipresent — left unconnected)
    for (const [phase, folders] of Object.entries(PHASE_SKILL_FOLDERS)) {
      const phaseId = `phase:${phase}`;
      if (!graph.hasNode(phaseId)) continue;
      for (const node of skillNodes) {
        const folder = (node.payload as { phase_folder?: string })?.phase_folder;
        if (folder && folders.includes(folder)) {
          const edgeId = `struct:${phaseId}:${node.id}`;
          if (!graph.hasEdge(edgeId)) {
            graph.addEdgeWithKey(edgeId, phaseId, node.id, {
              color: '#334155', size: 0.8, structural: true,
            });
          }
        }
      }
    }

    loadGraph(graph);
  }, [neurons, activeEvents, loadGraph]);

  // Activity edges from liveBatches -- mutate Sigma's LIVE graph directly
  useEffect(() => {
    const graph = sigma.getGraph();
    if (!graph || graph.order === 0) return;

    const now = Date.now() / 1000;
    for (const batch of liveBatches) {
      const batchId = batch._stream_id || `${batch.event_id}:${batch.timestamp}`;
      if (processedBatchesRef.current.has(batchId)) continue;
      processedBatchesRef.current.add(batchId);
      if (processedBatchesRef.current.size > 500) {
        const entries = [...processedBatchesRef.current];
        processedBatchesRef.current = new Set(entries.slice(-200));
      }

      // Skip stale batches on graph rebuild — only replay edges still within fade window (30s)
      if (now - batch.timestamp > 30) continue;

      const evtId = batch.event_id;
      if (!evtId) continue;

      if (!graph.hasNode(evtId)) {
        if (!activeEvents.some(e => e.id === evtId)) continue;
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

      for (let pulseIdx = 0; pulseIdx < batch.pulses.length; pulseIdx++) {
        const pulse = batch.pulses[pulseIdx];
        const edgeId = `activity:${evtId}:${pulse.neuron_id}:${batch.timestamp}`;
        if (graph.hasEdge(edgeId) || !graph.hasNode(pulse.neuron_id)) continue;

        // Record pulse time for temporal decay (breathing effect)
        lastPulseRef.current.set(pulse.neuron_id, Date.now());

        let source = evtId;
        let size = 4;
        let color = eventColor(evtId);

        if (pulse.neuron_type === 'phase') {
          size = 6;
        } else if (pulse.neuron_type === 'lesson' || pulse.neuron_type === 'memory' || pulse.neuron_type === 'knowledge') {
          size = 2;
          const lastTool = batch.pulses.findLast(p => p.neuron_type === 'tool');
          if (lastTool && graph.hasNode(lastTool.neuron_id)) source = lastTool.neuron_id;
        } else if (pulse.neuron_type === 'agent') {
          source = 'tool:select_agent';
          color = getNeuronColor({ type: 'agent', id: pulse.neuron_id });
          if (!graph.hasNode(source)) continue;
        } else if (pulse.neuron_type === 'skill') {
          size = 2;
          // Skill pulses arrive in a separate batch (no tool in same batch) — route from event node
          source = evtId;
        }

        // Sequential chain: stagger edge creation by 120ms per pulse for cascade effect
        const delay = pulseIdx * 120;
        const createEdge = () => {
          if (!graph.hasNode(source) || !graph.hasNode(pulse.neuron_id)) return;
          if (graph.hasEdge(edgeId)) return;

          graph.addEdgeWithKey(edgeId, source, pulse.neuron_id, { color, size, structural: false });

          // Temporal decay: briefly enlarge target node then decay back, emit spark on settle
          // Use baseSizeRef to avoid compounding when multiple pulses hit before decay completes
          if (!baseSizeRef.current.has(pulse.neuron_id)) {
            baseSizeRef.current.set(pulse.neuron_id, graph.getNodeAttribute(pulse.neuron_id, 'size') as number);
          }
          const baseSize = baseSizeRef.current.get(pulse.neuron_id)!;
          graph.setNodeAttribute(pulse.neuron_id, 'size', baseSize * 1.6);
          setTimeout(() => {
            if (!graph.hasNode(pulse.neuron_id)) return;
            graph.setNodeAttribute(pulse.neuron_id, 'size', baseSize * 1.2);
            setTimeout(() => {
              if (!graph.hasNode(pulse.neuron_id)) return;
              graph.setNodeAttribute(pulse.neuron_id, 'size', baseSize);
              // Emit glowing spark outward on settle
              const sparkContainer = sigma.getContainer();
              if (sparkContainer && graph.hasNode(pulse.neuron_id)) {
                const attrs = graph.getNodeAttributes(pulse.neuron_id);
                const vp = sigma.graphToViewport({ x: attrs.x as number, y: attrs.y as number });
                const angle = Math.random() * Math.PI * 2;
                const dist = 40 + Math.random() * 60;
                const spark = document.createElement('div');
                spark.className = 'neuron-spark';
                spark.style.left = `${vp.x - 3}px`;
                spark.style.top = `${vp.y - 3}px`;
                spark.style.color = attrs.color as string;
                spark.style.setProperty('--dx', `${Math.cos(angle) * dist}px`);
                spark.style.setProperty('--dy', `${Math.sin(angle) * dist}px`);
                sparkContainer.appendChild(spark);
                spark.addEventListener('animationend', () => spark.remove());
                setTimeout(() => spark.remove(), 1400);
              }
            }, 3000);
          }, 2000);

          // 10s solid, then 20s fade (reasoning trail persists longer)
          const createdAt = Date.now();
          const timer = window.setInterval(() => {
            if (!graph.hasEdge(edgeId)) { clearInterval(timer); return; }
            const elapsed = (Date.now() - createdAt) / 1000;
            if (elapsed < 10) return;
            const fadeElapsed = elapsed - 10;
            const linearOpacity = Math.max(0, 1.0 - fadeElapsed / 20);
            const opacity = linearOpacity * linearOpacity;
            if (opacity <= 0) {
              graph.dropEdge(edgeId);
              clearInterval(timer);
              activityTimersRef.current.delete(edgeId);
            } else {
              graph.setEdgeAttribute(edgeId, 'size', Math.max(0.5, size * opacity));
            }
          }, 1000);
          activityTimersRef.current.set(edgeId, timer);

          // Ripple overlay for skill pulses (capped at 10 concurrent)
          if (pulse.neuron_type === 'skill') {
            const container = sigma.getContainer();
            if (container && activeRipplesRef.current < 10) {
              activeRipplesRef.current++;
              const nodeAttrs = graph.getNodeAttributes(pulse.neuron_id);
              const viewPos = sigma.graphToViewport({ x: nodeAttrs.x as number, y: nodeAttrs.y as number });
              const ripple = document.createElement('div');
              ripple.className = 'skill-ripple';
              ripple.style.left = `${viewPos.x - 6}px`;
              ripple.style.top = `${viewPos.y - 6}px`;
              ripple.style.color = graph.getNodeAttribute(pulse.neuron_id, 'color') as string;
              container.appendChild(ripple);
              let cleaned = false;
              const cleanup = () => {
                if (cleaned) return;
                cleaned = true;
                ripple.remove();
                activeRipplesRef.current--;
              };
              ripple.addEventListener('animationend', cleanup);
              setTimeout(cleanup, 700);
            }
          }
        };

        if (delay > 0) { setTimeout(createEdge, delay); } else { createEdge(); }
      }
    }
  }, [liveBatches, sigma, activeEvents]);

  useEffect(() => {
    const timers = activityTimersRef.current;
    return () => { for (const t of timers.values()) clearInterval(t); };
  }, []);

  // Merged nodeReducer: dimmed + glow in one pass
  useEffect(() => {
    if (!sigma.getGraph()) return;

    sigma.setSetting('nodeReducer', (node, data) => {
      if (dimmedIds?.has(node)) return { ...data, color: '#1e293b', size: 2, label: '' };
      if (glowingIds.has(node)) {
        const glowData: Record<string, unknown> = { ...data, color: '#fbbf24', size: (data.size ?? 4) * 1.8 };
        // Reveal skill labels when glowing (normally hidden)
        if (node.startsWith('skill:')) {
          const n = neurons.find(nn => nn.id === node);
          if (n) glowData.label = (n.payload?.label as string) ?? node.slice(6);
        }
        return glowData;
      }
      return data;
    });

    sigma.refresh();
  }, [glowingIds, dimmedIds, sigma, neurons]);

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

const NavigationControls: FC = () => {
  const sigma = useSigma();
  const fitted = useRef(false);

  useEffect(() => {
    if (!fitted.current && sigma.getGraph()?.order > 0) {
      fitted.current = true;
      setTimeout(() => sigma.getCamera().animatedReset({ duration: 300 }), 100);
    }
  }, [sigma]);

  const zoomIn = () => {
    const camera = sigma.getCamera();
    camera.animatedZoom({ duration: 200, factor: 1.5 });
  };
  const zoomOut = () => {
    const camera = sigma.getCamera();
    camera.animatedUnzoom({ duration: 200, factor: 1.5 });
  };
  const fitToView = () => {
    sigma.getCamera().animatedReset({ duration: 300 });
  };

  return (
    <div style={{
      position: 'absolute', bottom: 12, right: 12, zIndex: 10,
      display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      <button onClick={zoomIn} style={navBtnStyle} title="Zoom in">+</button>
      <button onClick={zoomOut} style={navBtnStyle} title="Zoom out">−</button>
      <button onClick={fitToView} style={navBtnStyle} title="Fit to view">⊙</button>
    </div>
  );
};

const navBtnStyle: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 4,
  background: '#1e293b', border: '1px solid #334155', color: '#94a3b8',
  fontSize: 16, lineHeight: '26px', textAlign: 'center',
  cursor: 'pointer', padding: 0,
};

const DragHandler: FC<{ onClick?: (id: string | null, pos?: { x: number; y: number }) => void }> = ({ onClick }) => {
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
      mouseup: (e) => {
        if (!dragStateRef.current) return;
        const { node, dragged, wasFixed } = dragStateRef.current;
        const graph = sigma.getGraph();
        graph.setNodeAttribute(node, 'fixed', wasFixed);
        dragStateRef.current = null;
        sigma.getCamera().enable();
        if (!dragged && onClick && e.original instanceof MouseEvent) {
          onClick(node, { x: e.original.clientX, y: e.original.clientY });
        }
      },
      clickStage: () => { onClick?.(null); },
      downStage: () => { onClick?.(null); },
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
  onClickNeuron?: (id: string | null, pos?: { x: number; y: number }) => void;
  className?: string;
}

export default function CortexGraph({
  neurons, glowingIds, activeEvents = [], liveBatches = [],
  dimmedIds, onClickNeuron, className,
}: CortexGraphProps) {
  return (
    <div className={`relative ${className ?? ''}`} style={{ background: '#030712', width: '100%', height: '100%' }}>
      <SigmaContainer
        graph={MultiGraph}
        style={{ width: '100%', height: '100%', background: 'transparent', position: 'relative' }}
        settings={{
          allowInvalidContainer: true,
          defaultNodeColor: '#475569',
          defaultEdgeColor: '#1e293b',
          labelColor: { color: '#94a3b8' },
          labelFont: 'Inter, system-ui, sans-serif',
          labelSize: 10,
          labelRenderedSizeThreshold: 4,
          renderLabels: true,
          enableEdgeEvents: false,
          stagePadding: 30,
          nodeProgramClasses: {
            circle: NodeCircleProgram,
            square: NodeSquareProgram,
          },
        }}
      >
        <GraphLoader
          neurons={neurons}
          glowingIds={glowingIds}
          activeEvents={activeEvents}
          liveBatches={liveBatches}
          dimmedIds={dimmedIds}
        />
        <FA2Controller />
        <DragHandler onClick={onClickNeuron} />
        <NavigationControls />
      </SigmaContainer>
    </div>
  );
}
