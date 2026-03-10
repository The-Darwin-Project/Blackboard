// BlackBoard/ui/src/components/graph/ArchitectureGraph.tsx
// @ai-rules:
// 1. [Pattern]: dagre layout memoized by node/edge ID hash. Data-only updates (CPU%, health) don't trigger relayout.
// 2. [Pattern]: Custom nodeTypes registered at module scope to avoid React Flow re-mount.
// 3. [Constraint]: Container must have explicit dimensions (h-full w-full) for React Flow.
import { useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  type Node,
  type Edge,
  type NodeMouseHandler,
  BackgroundVariant,
  ReactFlowProvider,
} from '@xyflow/react';
import Dagre from '@dagrejs/dagre';
import { Loader2 } from 'lucide-react';
import { useGraph } from '../../hooks';
import type { GraphResponse } from '../../api/types';
import ServiceNode from './ServiceNode';
import TicketNode from './TicketNode';

const nodeTypes = { service: ServiceNode, ticket: TicketNode };

interface Props {
  onNodeClick?: (serviceName: string) => void;
}

function computeIdHash(data: GraphResponse): string {
  const nodeIds = data.nodes.map((n) => n.id).sort().join(',');
  const edgeIds = data.edges.map((e) => `${e.source}-${e.target}`).sort().join(',');
  const ticketIds = (data.tickets ?? []).map((t) => t.event_id).sort().join(',');
  return `${nodeIds}|${edgeIds}|${ticketIds}`;
}

function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    const w = node.type === 'ticket' ? 170 : 240;
    g.setNode(node.id, { width: w, height: 100 });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  Dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    const w = node.type === 'ticket' ? 170 : 240;
    return { ...node, position: { x: pos.x - w / 2, y: pos.y - 50 } };
  });
}

function buildGraph(data: GraphResponse): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  data.nodes.forEach((gn) => {
    if (!gn.id) return;
    nodes.push({
      id: gn.id,
      type: 'service',
      position: { x: 0, y: 0 },
      data: {
        label: gn.label,
        type: gn.type,
        ...gn.metadata,
      },
    });
  });

  data.edges.forEach((ge, idx) => {
    if (!ge.source || !ge.target) return;
    edges.push({
      id: `edge-${idx}`,
      source: ge.source,
      target: ge.target,
      animated: ge.type === 'async',
      style: { stroke: '#475569', strokeWidth: 1.5 },
    });
  });

  (data.tickets ?? []).forEach((ticket) => {
    const ticketId = `ticket-${ticket.event_id}`;
    nodes.push({
      id: ticketId,
      type: 'ticket',
      position: { x: 0, y: 0 },
      data: { ...ticket },
    });

    if (ticket.resolved_service) {
      edges.push({
        id: `ticket-edge-${ticket.event_id}`,
        source: ticketId,
        target: ticket.resolved_service,
        style: { stroke: '#f59e0b', strokeDasharray: '5 3', strokeWidth: 1.5 },
      });
    }
  });

  const laid = applyDagreLayout(nodes, edges);
  return { nodes: laid, edges };
}

function ArchitectureGraphInner({ onNodeClick }: Props) {
  const { data, isLoading } = useGraph();
  const prevHashRef = useRef<string>('');
  const prevLayoutRef = useRef<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] });

  const { nodes, edges } = useMemo(() => {
    if (!data?.nodes?.length) return { nodes: [], edges: [] };

    const hash = computeIdHash(data);
    if (hash === prevHashRef.current) {
      const prev = prevLayoutRef.current;
      const fresh = buildGraph(data);
      const merged = prev.nodes.map((pn) => {
        const fn = fresh.nodes.find((n) => n.id === pn.id);
        return fn ? { ...pn, data: fn.data } : pn;
      });
      const added = fresh.nodes.filter((fn) => !prev.nodes.some((pn) => pn.id === fn.id));
      return { nodes: [...merged, ...added], edges: fresh.edges };
    }

    const result = buildGraph(data);
    prevHashRef.current = hash;
    prevLayoutRef.current = result;
    return result;
  }, [data]);

  const handleNodeClick: NodeMouseHandler = useCallback((_event, node) => {
    if (node.type === 'ticket') return;
    onNodeClick?.(node.id);
  }, [onNodeClick]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading architecture graph...
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
        No topology data available.
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Controls showInteractive={false} />
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
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
