// BlackBoard/ui/src/components/cortex/CortexGraph.tsx
// @ai-rules:
// 1. [Pattern]: SigmaContainer + useLoadGraph + useRegisterEvents from @react-sigma/core.
// 2. [Constraint]: Knowledge neurons positioned left via ForceAtlas2, executive neurons fixed right.
// 3. [Gotcha]: Sigma node reducers run per-frame -- keep isGlowing check cheap (Map lookup).
// 4. [Pattern]: Node click dispatches onSelectNeuron callback for drill-down.
import { useEffect, useRef, type FC } from 'react';
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import '@react-sigma/core/lib/style.css';
import { NEURON_COLORS, AGENT_NEURON_COLORS } from '../../constants/colors';
import { getExecutiveNeurons, HEMISPHERE_X, TOOL_GROUP_Y } from './cortex-constants';
import type { Neuron } from './types';

function getNeuronColor(neuron: { type: string; id: string }): string {
  if (neuron.type === 'agent') {
    const name = neuron.id.replace('agent:', '');
    return AGENT_NEURON_COLORS[name] ?? NEURON_COLORS.agent;
  }
  return NEURON_COLORS[neuron.type] ?? '#6b7280';
}

function getNeuronSize(heat: number, type: string): number {
  const base = type === 'tool' || type === 'phase' ? 4 : type === 'agent' ? 6 : 3;
  return base + Math.min(heat * 0.3, 12);
}

interface GraphLoaderProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
}

const GraphLoader: FC<GraphLoaderProps> = ({ neurons, glowingIds }) => {
  const loadGraph = useLoadGraph();
  const sigma = useSigma();
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    const graph = new Graph();
    const executive = getExecutiveNeurons();
    const allNeurons = [...neurons, ...executive];
    const heatMap = new Map(neurons.map(n => [n.id, n.heat]));

    for (const execN of executive) {
      if (heatMap.has(execN.id)) {
        execN.heat = heatMap.get(execN.id)!;
      }
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

    // Run ForceAtlas2 only on knowledge hemisphere nodes
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
      // Restore executive positions (ForceAtlas2 moves all nodes)
      for (const n of allNeurons) {
        if (n.type !== 'lesson' && n.type !== 'memory' && graph.hasNode(n.id)) {
          const attrs = graph.getNodeAttributes(n.id);
          // re-apply fixed positions for executive
          if (n.type === 'tool') {
            const group = (n.payload?.group as string) ?? 'observation';
            graph.setNodeAttribute(n.id, 'x', HEMISPHERE_X.executive + (attrs.x % 80));
            graph.setNodeAttribute(n.id, 'y', (TOOL_GROUP_Y[group] ?? 0) + (attrs.y % 30));
          }
        }
      }
    }

    graphRef.current = graph;
    loadGraph(graph);
  }, [neurons, loadGraph]);

  // Glow effect via node reducer
  useEffect(() => {
    const renderer = sigma.getGraph() ? sigma : null;
    if (!renderer) return;
    sigma.setSetting('nodeReducer', (node, data) => {
      const res = { ...data };
      if (glowingIds.has(node)) {
        res.color = '#fbbf24';
        res.size = (data.size ?? 4) * 1.5;
      }
      return res;
    });
    sigma.refresh();
  }, [glowingIds, sigma]);

  return null;
};

interface CortexGraphProps {
  neurons: Neuron[];
  glowingIds: Set<string>;
  dimmedIds?: Set<string>;
  onClickNeuron?: (id: string) => void;
  className?: string;
}

export default function CortexGraph({ neurons, glowingIds, dimmedIds, onClickNeuron, className }: CortexGraphProps) {
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
          labelRenderedSizeThreshold: 6,
          renderLabels: true,
          enableEdgeEvents: false,
          ...(dimmedIds ? {
            nodeReducer: (node: string, data: Record<string, unknown>) => {
              if (dimmedIds.has(node)) return { ...data, color: '#1e293b', size: 2, label: '' };
              return data;
            },
          } : {}),
        }}
      >
        <GraphLoader neurons={neurons} glowingIds={glowingIds} />
        {onClickNeuron && <ClickHandler onClick={onClickNeuron} />}
      </SigmaContainer>
    </div>
  );
}

const ClickHandler: FC<{ onClick: (id: string) => void }> = ({ onClick }) => {
  const registerEvents = useRegisterEvents();

  useEffect(() => {
    registerEvents({
      clickNode: (event) => onClick(event.node),
    });
  }, [registerEvents, onClick]);

  return null;
};
