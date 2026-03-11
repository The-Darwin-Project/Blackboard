// BlackBoard/ui/src/components/graph/ArchitectureGraph.tsx
// @ai-rules:
// 1. [Pattern]: Layout memoized by node/edge ID hash + layout type. Data-only updates don't trigger relayout.
// 2. [Pattern]: Custom nodeTypes/edgeTypes registered at module scope to avoid React Flow re-mount.
// 3. [Constraint]: Container must have explicit dimensions for React Flow.
// 4. [Pattern]: Three layouts: dagre-TB, dagre-LR, grid. Persisted in localStorage.
// 5. [Pattern]: Uses useNodesState/useEdgesState for proper React Flow controlled state.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Controls,
  Background,
  type Node,
  type Edge,
  type NodeMouseHandler,
  BackgroundVariant,
  ReactFlowProvider,
} from '@xyflow/react';
import Dagre from '@dagrejs/dagre';
import { Loader2, LayoutGrid, ArrowDown, ArrowRight } from 'lucide-react';
import { useGraph } from '../../hooks';
import type { GraphResponse } from '../../api/types';
import ServiceNode from './ServiceNode';
import TicketNode from './TicketNode';
import DarwinEdge from './DarwinEdge';
import './ArchitectureGraph.css';

const nodeTypes = { service: ServiceNode, ticket: TicketNode };
const edgeTypes = { darwin: DarwinEdge };
type LayoutType = 'dagre-tb' | 'dagre-lr' | 'grid';
const LAYOUT_KEY = 'darwin:graph:layout';

interface Props {
  onNodeClick?: (serviceName: string) => void;
  onTicketClick?: (eventId: string) => void;
}

function nodeWidth(type: string | undefined): number {
  return type === 'ticket' ? 180 : 240;
}

function computeIdHash(data: GraphResponse, layout: LayoutType): string {
  const nIds = data.nodes.map((n) => n.id).sort().join(',');
  const eIds = data.edges.map((e) => `${e.source}-${e.target}`).sort().join(',');
  const tIds = (data.tickets ?? []).map((t) => t.event_id).sort().join(',');
  return `${layout}|${nIds}|${eIds}|${tIds}`;
}

function applyDagreLayout(nodes: Node[], edges: Edge[], rankdir: 'TB' | 'LR'): Node[] {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir, nodesep: 80, ranksep: rankdir === 'LR' ? 200 : 100, marginx: 40, marginy: 40 });

  nodes.forEach((n) => g.setNode(n.id, { width: nodeWidth(n.type), height: 120 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  Dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - nodeWidth(n.type) / 2, y: pos.y - 60 } };
  });
}

function applyGridLayout(nodes: Node[]): Node[] {
  const tickets = nodes.filter((n) => n.type === 'ticket');
  const services = nodes.filter((n) => n.type !== 'ticket');
  const cols = Math.max(3, Math.ceil(Math.sqrt(services.length)));
  const result: Node[] = [];

  tickets.forEach((n, i) => result.push({ ...n, position: { x: i * 210, y: 0 } }));
  const yOff = tickets.length > 0 ? 160 : 0;
  services.forEach((n, i) => {
    result.push({ ...n, position: { x: (i % cols) * 280, y: yOff + Math.floor(i / cols) * 160 } });
  });
  return result;
}

function applyLayout(nodes: Node[], edges: Edge[], layout: LayoutType): Node[] {
  if (layout === 'grid') return applyGridLayout(nodes);
  return applyDagreLayout(nodes, edges, layout === 'dagre-lr' ? 'LR' : 'TB');
}

function buildGraph(data: GraphResponse, layout: LayoutType): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  data.nodes.forEach((gn) => {
    if (!gn.id) return;
    nodes.push({
      id: gn.id, type: 'service', position: { x: 0, y: 0 },
      data: { label: gn.label, type: gn.type, ...gn.metadata },
    });
  });

  data.edges.forEach((ge, idx) => {
    if (!ge.source || !ge.target) return;
    edges.push({
      id: `edge-${idx}`, source: ge.source, target: ge.target,
      type: 'darwin', data: { async: ge.type === 'async' },
    });
  });

  (data.tickets ?? []).forEach((ticket) => {
    const tid = `ticket-${ticket.event_id}`;
    nodes.push({ id: tid, type: 'ticket', position: { x: 0, y: 0 }, data: { ...ticket } });
    if (ticket.resolved_service) {
      edges.push({
        id: `ticket-edge-${ticket.event_id}`, source: tid, target: ticket.resolved_service,
        type: 'darwin', data: { ticket: true },
      });
    }
  });

  return { nodes: applyLayout(nodes, edges, layout), edges };
}

const LAYOUT_OPTIONS: { value: LayoutType; icon: typeof LayoutGrid; label: string }[] = [
  { value: 'grid', icon: LayoutGrid, label: 'Grid' },
  { value: 'dagre-tb', icon: ArrowDown, label: 'Top-Down' },
  { value: 'dagre-lr', icon: ArrowRight, label: 'Left-Right' },
];

function ArchitectureGraphInner({ onNodeClick, onTicketClick }: Props) {
  const { data, isLoading } = useGraph();
  const { fitView } = useReactFlow();
  const [layout, setLayout] = useState<LayoutType>(
    () => (localStorage.getItem(LAYOUT_KEY) as LayoutType) || 'grid',
  );
  const prevHashRef = useRef('');
  const structureChangedRef = useRef(false);

  const { rfNodes, rfEdges } = useMemo(() => {
    if (!data?.nodes?.length) return { rfNodes: [], rfEdges: [] };

    const hash = computeIdHash(data, layout);
    structureChangedRef.current = hash !== prevHashRef.current;
    prevHashRef.current = hash;

    const built = buildGraph(data, layout);
    return { rfNodes: built.nodes, rfEdges: built.edges };
  }, [data, layout]);

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges);

  useEffect(() => {
    setNodes(rfNodes);
    setEdges(rfEdges);
    if (structureChangedRef.current) {
      requestAnimationFrame(() => fitView({ padding: 0.15, duration: 300 }));
    }
  }, [rfNodes, rfEdges, setNodes, setEdges, fitView]);

  const changeLayout = useCallback((l: LayoutType) => {
    setLayout(l);
    localStorage.setItem(LAYOUT_KEY, l);
    prevHashRef.current = '';
  }, []);

  const handleNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    if (node.type === 'ticket') {
      const eventId = (node.data as { event_id?: string }).event_id;
      if (eventId) onTicketClick?.(eventId);
      return;
    }
    onNodeClick?.(node.id);
  }, [onNodeClick, onTicketClick]);

  if (isLoading) {
    return (
      <div className="arch-graph-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#9ca3af', marginRight: 8 }} />
        <span style={{ color: '#9ca3af' }}>Loading topology...</span>
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div className="arch-graph-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', fontSize: 13 }}>
        No topology data available.
      </div>
    );
  }

  return (
    <div className="arch-graph-container">
      <div className="arch-layout-toolbar">
        {LAYOUT_OPTIONS.map((opt) => {
          const Icon = opt.icon;
          return (
            <button
              key={opt.value}
              onClick={() => changeLayout(opt.value)}
              title={opt.label}
              className={`arch-layout-btn${layout === opt.value ? ' arch-layout-btn-active' : ''}`}
            >
              <Icon size={14} />
            </button>
          );
        })}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={handleNodeClick}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        snapToGrid
        snapGrid={[20, 20]}
        nodesConnectable={false}
      >
        <Controls position="top-right" showInteractive={false} />
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1f2937" />
      </ReactFlow>
    </div>
  );
}

export default function ArchitectureGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <ArchitectureGraphInner {...props} />
    </ReactFlowProvider>
  );
}
