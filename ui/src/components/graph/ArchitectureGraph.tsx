// BlackBoard/ui/src/components/graph/ArchitectureGraph.tsx
// @ai-rules:
// 1. [Pattern]: Layout memoized by node/edge ID hash + layout type. Data-only updates don't trigger relayout.
// 2. [Pattern]: Custom nodeTypes/edgeTypes registered at module scope to avoid React Flow re-mount.
// 3. [Constraint]: Container must have explicit dimensions for React Flow.
// 4. [Pattern]: Three layouts: dagre-TB, dagre-LR, grid. Persisted in localStorage. Grid is the
//    default -- edges are always empty now (namespace grouping replaced them), so dagre's
//    rank-based layout degrades to a single row/column; grid is the reliable default.
// 5. [Pattern]: Uses useNodesState/useEdgesState for proper React Flow controlled state.
// 6. [Pattern]: Namespace group nodes (type: 'group') are pushed into the nodes array BEFORE
//    their service-node children -- React Flow requires parents to precede children for
//    correct z-index and coordinate-system resolution. Child positions are always RELATIVE
//    to the parent group's position (React Flow's `parentId` contract), never absolute.
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
import NamespaceGroupNode from './NamespaceGroupNode';
import DarwinEdge from './DarwinEdge';
import './ArchitectureGraph.css';

const nodeTypes = { service: ServiceNode, ticket: TicketNode, group: NamespaceGroupNode };
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
  const nsIds = Array.from(new Set(data.nodes.map((n) => n.metadata.namespace).filter(Boolean))).sort().join(',');
  const tIds = (data.tickets ?? []).map((t) => t.event_id).sort().join(',');
  return `${layout}|${nIds}|${nsIds}|${tIds}`;
}

// --- Grid layout: groups laid out first (flow-wrapping row of boxes), then each
// group's children positioned in a mini-grid RELATIVE to that group's origin. ---

const GROUP_PADDING = 36;
const GROUP_HEADER = 34;
const GROUP_GAP = 40;
const MAX_ROW_WIDTH = 1400;
const CELL_W = 264;
const CELL_H = 150;

function layoutGroupChildren(children: Node[]): { nodes: Node[]; width: number; height: number } {
  const cols = Math.max(1, Math.min(4, Math.ceil(Math.sqrt(children.length))));
  const rows = Math.max(1, Math.ceil(children.length / cols));
  const positioned = children.map((n, i) => ({
    ...n,
    position: {
      x: GROUP_PADDING + (i % cols) * CELL_W,
      y: GROUP_HEADER + Math.floor(i / cols) * CELL_H,
    },
  }));
  const width = GROUP_PADDING * 2 + cols * CELL_W - (CELL_W - 240);
  const height = GROUP_HEADER + GROUP_PADDING + rows * CELL_H - (CELL_H - 120);
  return { nodes: positioned, width, height };
}

function applyGridLayout(nodes: Node[]): Node[] {
  const tickets = nodes.filter((n) => n.type === 'ticket');
  const groups = nodes.filter((n) => n.type === 'group');
  const services = nodes.filter((n) => n.type !== 'ticket' && n.type !== 'group');
  const result: Node[] = [];

  tickets.forEach((n, i) => result.push({ ...n, position: { x: i * 210, y: 0 } }));
  const yOff = tickets.length > 0 ? 160 : 0;

  if (groups.length === 0) {
    // No namespace metadata available -- fall back to a flat grid (legacy behavior).
    const cols = Math.max(3, Math.ceil(Math.sqrt(services.length)));
    services.forEach((n, i) => {
      result.push({ ...n, position: { x: (i % cols) * 280, y: yOff + Math.floor(i / cols) * 160 } });
    });
    return result;
  }

  let cursorX = 0;
  let cursorY = yOff;
  let rowHeight = 0;

  groups.forEach((group) => {
    const children = services.filter((s) => s.parentId === group.id);
    const { nodes: laidOutChildren, width, height } = layoutGroupChildren(children);

    if (cursorX > 0 && cursorX + width > MAX_ROW_WIDTH) {
      cursorX = 0;
      cursorY += rowHeight + GROUP_GAP;
      rowHeight = 0;
    }

    result.push({ ...group, position: { x: cursorX, y: cursorY }, style: { width, height } });
    laidOutChildren.forEach((child) => result.push(child));

    cursorX += width + GROUP_GAP;
    rowHeight = Math.max(rowHeight, height);
  });

  // Ungrouped services (no namespace) render below all groups, flat grid.
  const ungrouped = services.filter((s) => !s.parentId);
  if (ungrouped.length > 0) {
    const cols = Math.max(3, Math.ceil(Math.sqrt(ungrouped.length)));
    const ungroupedY = cursorY + rowHeight + (rowHeight > 0 ? GROUP_GAP : 0);
    ungrouped.forEach((n, i) => {
      result.push({ ...n, position: { x: (i % cols) * 280, y: ungroupedY + Math.floor(i / cols) * 160 } });
    });
  }

  return result;
}

// --- Dagre layout: kept as an option. Without edges, dagre has no ranking signal, so
// this degrades to compound-only positioning (groups sized around their children). ---

function applyDagreLayout(nodes: Node[], edges: Edge[], rankdir: 'TB' | 'LR'): Node[] {
  const g = new Dagre.graphlib.Graph({ compound: true }).setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir, nodesep: 80, ranksep: rankdir === 'LR' ? 200 : 100, marginx: 40, marginy: 40 });

  const groups = nodes.filter((n) => n.type === 'group');
  const nonGroups = nodes.filter((n) => n.type !== 'group');

  groups.forEach((gr) => g.setNode(gr.id, { width: 10, height: 10 }));
  nonGroups.forEach((n) => g.setNode(n.id, { width: nodeWidth(n.type), height: 120 }));
  nonGroups.forEach((n) => {
    if (n.parentId) g.setParent(n.id, n.parentId);
  });
  edges.forEach((e) => g.setEdge(e.source, e.target));
  Dagre.layout(g);

  const positionedGroups = groups.map((gr) => {
    const pos = g.node(gr.id);
    return { ...gr, position: { x: pos.x - pos.width / 2, y: pos.y - pos.height / 2 }, style: { width: pos.width, height: pos.height } };
  });

  const positionedNodes = nonGroups.map((n) => {
    const pos = g.node(n.id);
    const parent = n.parentId ? g.node(n.parentId) : null;
    // Dagre returns absolute coordinates; React Flow requires child positions
    // relative to the parent when `parentId` is set.
    const x = parent
      ? pos.x - (parent.x - parent.width / 2) - nodeWidth(n.type) / 2
      : pos.x - nodeWidth(n.type) / 2;
    const y = parent
      ? pos.y - (parent.y - parent.height / 2) - 60
      : pos.y - 60;
    return { ...n, position: { x, y } };
  });

  return [...positionedGroups, ...positionedNodes];
}

function applyLayout(nodes: Node[], edges: Edge[], layout: LayoutType): Node[] {
  if (layout === 'grid') return applyGridLayout(nodes);
  return applyDagreLayout(nodes, edges, layout === 'dagre-lr' ? 'LR' : 'TB');
}

function buildGraph(data: GraphResponse, layout: LayoutType): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Namespace group (parent) nodes -- pushed first so React Flow renders/orders them
  // before their service-node children.
  const namespaces = Array.from(
    new Set(data.nodes.map((gn) => gn.metadata.namespace).filter((ns): ns is string => !!ns)),
  ).sort();

  namespaces.forEach((ns) => {
    nodes.push({
      id: `group-${ns}`,
      type: 'group',
      position: { x: 0, y: 0 },
      data: { label: ns },
      style: { width: 300, height: 200 },
      selectable: false,
    });
  });

  data.nodes.forEach((gn) => {
    if (!gn.id) return;
    const namespace = gn.metadata.namespace;
    nodes.push({
      id: gn.id,
      type: 'service',
      position: { x: 0, y: 0 },
      ...(namespace ? { parentId: `group-${namespace}`, extent: 'parent' as const } : {}),
      data: { label: gn.label, type: gn.type, ...gn.metadata },
    });
  });

  // Backend edges are always empty now (namespace grouping replaced the env-var
  // dependency heuristic). Ticket->resolved_service edges below are the only
  // remaining edge source (currently dormant -- resolved_service is always null).
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
    if (node.type === 'group') return;
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
