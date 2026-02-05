// BlackBoard/ui/src/components/CytoscapeGraph.tsx
/**
 * Cytoscape.js-based architecture graph visualization.
 * 
 * Features:
 * - Health-based node colors (green/yellow/red/grey)
 * - Node type icons (service/database/cache/external)
 * - Ghost nodes for pending plans
 * - cose-bilkent auto-layout
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import nodeHtmlLabel from 'cytoscape-node-html-label';
import { Loader2, Network } from 'lucide-react';
import { useGraph } from '../hooks';
import type { GraphNode, GhostNode, HealthStatus, NodeType } from '../api/types';

// Register extensions safely (only once, with error handling)
let extensionsRegistered = false;
try {
  if (!extensionsRegistered) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (cytoscape as any).use(coseBilkent);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (cytoscape as any).use(nodeHtmlLabel);
    extensionsRegistered = true;
    console.log('[CytoscapeGraph] Extensions registered successfully');
  }
} catch (err) {
  console.warn('[CytoscapeGraph] Failed to register extensions:', err);
}

// Health colors matching GRAPH_SPEC
const HEALTH_COLORS: Record<HealthStatus, string> = {
  healthy: '#22c55e',   // Green
  warning: '#eab308',   // Yellow
  critical: '#ef4444',  // Red
  unknown: '#64748b',   // Grey
};

// Node type icons
const NODE_ICONS: Record<NodeType, string> = {
  service: '📦',
  database: '🛢️',
  cache: '⚡',
  external: '☁️',
};

// Layout configuration (cose-bilkent with fallback to built-in cose)
const LAYOUT_OPTIONS = extensionsRegistered
  ? {
      name: 'cose-bilkent',
      animate: false,
      nodeDimensionsIncludeLabels: true,
      idealEdgeLength: 120,
      nodeRepulsion: 5000,
      gravity: 0.3,
      numIter: 2500,
      tile: true,
    }
  : {
      // Fallback to built-in cose layout
      name: 'cose',
      animate: false,
      nodeDimensionsIncludeLabels: true,
      idealEdgeLength: 120,
      nodeRepulsion: 5000,
      gravity: 0.3,
    };

interface CytoscapeGraphProps {
  onNodeClick?: (serviceName: string) => void;
  onPlanClick?: (planId: string) => void;
}

function CytoscapeGraph({ onNodeClick, onPlanClick }: CytoscapeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cyRef = useRef<any>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const { data, isLoading, isError } = useGraph();

  // Build node HTML label
  const buildNodeLabel = useCallback((node: GraphNode) => {
    const icon = NODE_ICONS[node.type] || '📦';
    const health = node.metadata.health || 'unknown';
    const version = node.metadata.version || '?';
    const cpu = node.metadata.cpu?.toFixed(0) || '0';
    const mem = node.metadata.memory?.toFixed(0) || '0';
    
    return `
      <div class="cyto-node-label" style="
        background: ${HEALTH_COLORS[health]};
        border-radius: 8px;
        padding: 6px 10px;
        color: ${health === 'warning' ? '#000' : '#fff'};
        font-size: 11px;
        text-align: center;
        min-width: 80px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      ">
        <div style="font-size: 16px; margin-bottom: 2px;">${icon}</div>
        <div style="font-weight: 600; margin-bottom: 2px;">${node.label}</div>
        <div style="font-size: 9px; opacity: 0.9;">v${version}</div>
        <div style="font-size: 9px; opacity: 0.8;">CPU:${cpu}% MEM:${mem}%</div>
      </div>
    `;
  }, []);

  // Build ghost node HTML label
  const buildGhostLabel = useCallback((ghost: GhostNode) => {
    return `
      <div class="cyto-ghost-label" style="
        background: rgba(99, 102, 241, 0.3);
        border: 2px dashed #6366f1;
        border-radius: 8px;
        padding: 6px 10px;
        color: #a5b4fc;
        font-size: 11px;
        text-align: center;
        min-width: 80px;
      ">
        <div style="font-size: 14px; margin-bottom: 2px;">👻</div>
        <div style="font-weight: 600; text-transform: uppercase;">${ghost.action}</div>
        <div style="font-size: 9px; opacity: 0.8;">${ghost.target_node}</div>
      </div>
    `;
  }, []);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cy = (cytoscape as any)({
      container: containerRef.current,
      style: [
        // Base node style (invisible - HTML labels handle appearance)
        {
          selector: 'node',
          style: {
            'width': 100,
            'height': 70,
            'shape': 'round-rectangle',
            'background-opacity': 0,
            'border-width': 0,
          },
        },
        // Ghost node style
        {
          selector: 'node.ghost',
          style: {
            'width': 90,
            'height': 60,
            'opacity': 0.7,
          },
        },
        // Edge styles
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#64748b',
            'target-arrow-color': '#64748b',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
          },
        },
        {
          selector: 'edge[type="async"]',
          style: {
            'line-style': 'dashed',
          },
        },
        {
          selector: 'edge.ghost-edge',
          style: {
            'line-style': 'dotted',
            'line-color': '#6366f1',
            'target-arrow-color': '#6366f1',
            'opacity': 0.5,
          },
        },
        // Edge labels
        {
          selector: 'edge[protocol]',
          style: {
            'label': 'data(protocol)',
            'font-size': 9,
            'color': '#94a3b8',
            'text-background-color': '#0f172a',
            'text-background-opacity': 0.8,
            'text-background-padding': '2px',
          },
        },
      ],
      // Disable default interactions we'll handle manually
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;
    setIsInitialized(true);

    return () => {
      // Clean up HTML labels before destroying Cytoscape
      cleanupHtmlLabels();
      cy.destroy();
      cyRef.current = null;
      setIsInitialized(false);
    };
  }, []);

  // Helper to clean up HTML labels (prevents memory leaks)
  const cleanupHtmlLabels = useCallback(() => {
    // Remove all cytoscape-node-html-label DOM elements
    const container = containerRef.current;
    if (container) {
      const labelContainers = container.querySelectorAll('.cytoscape-node-html-label');
      labelContainers.forEach((el) => el.remove());
    }
  }, []);

  // Handle node clicks
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const handleTap = (evt: any) => {
      const node = evt.target;
      if (node.isNode()) {
        const nodeData = node.data();
        if (nodeData.isGhost && onPlanClick) {
          onPlanClick(nodeData.planId);
        } else if (onNodeClick) {
          onNodeClick(nodeData.id);
        }
      }
    };

    cy.on('tap', 'node', handleTap);
    return () => {
      cy.off('tap', 'node', handleTap);
    };
  }, [onNodeClick, onPlanClick]);

  // Update graph when data changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !data || !isInitialized) return;

    // Build elements
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const elements: any[] = [];

    // Add nodes
    data.nodes.forEach((node) => {
      elements.push({
        data: {
          id: node.id,
          label: node.label,
          type: node.type,
          ...node.metadata,  // includes health, version, cpu, memory, etc.
        },
      });
    });

    // Add edges
    data.edges.forEach((edge, idx) => {
      elements.push({
        data: {
          id: `edge-${idx}`,
          source: edge.source,
          target: edge.target,
          protocol: edge.protocol,
          type: edge.type,
        },
      });
    });

    // Add ghost nodes from pending plans
    data.plans.forEach((plan) => {
      const ghostId = `ghost-${plan.plan_id}`;
      
      // Ghost node
      elements.push({
        data: {
          id: ghostId,
          label: `${plan.action}: ${plan.target_node}`,
          isGhost: true,
          planId: plan.plan_id,
          action: plan.action,
        },
        classes: 'ghost',
      });

      // Ghost edge connecting to target
      elements.push({
        data: {
          id: `ghost-edge-${plan.plan_id}`,
          source: plan.target_node,
          target: ghostId,
        },
        classes: 'ghost-edge',
      });
    });

    // Clean up existing HTML labels before removing elements (prevents memory leaks)
    cleanupHtmlLabels();
    
    // Update graph
    cy.elements().remove();
    cy.add(elements);

    // Apply HTML labels
    cy.nodeHtmlLabel([
      {
        query: 'node:not(.ghost)',
        halign: 'center',
        valign: 'center',
        halignBox: 'center',
        valignBox: 'center',
        tpl: (nodeData: unknown) => {
          const d = nodeData as GraphNode['metadata'] & { id: string; label: string; type: NodeType };
          return buildNodeLabel({
            id: d.id,
            type: d.type,
            label: d.label,
            metadata: {
              version: d.version,
              health: d.health as HealthStatus,
              cpu: d.cpu,
              memory: d.memory,
              error_rate: d.error_rate,
              last_seen: d.last_seen,
            },
          });
        },
      },
      {
        query: 'node.ghost',
        halign: 'center',
        valign: 'center',
        halignBox: 'center',
        valignBox: 'center',
        tpl: (nodeData: unknown) => {
          const d = nodeData as { planId: string; action: string; label: string };
          return buildGhostLabel({
            plan_id: d.planId,
            target_node: d.label.split(': ')[1] || '',
            action: d.action,
            status: 'pending',
            params: {},
          });
        },
      },
    ]);

    // Run layout
    cy.layout(LAYOUT_OPTIONS).run();

    // Fit to viewport with padding
    cy.fit(undefined, 30);

  }, [data, isInitialized, buildNodeLabel, buildGhostLabel, cleanupHtmlLabels]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <Network className="w-12 h-12" />
        <p className="text-sm">Unable to load graph</p>
        <p className="text-xs">Check API connection</p>
      </div>
    );
  }

  if (!data?.nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <Network className="w-12 h-12" />
        <p className="text-sm">No services registered</p>
        <p className="text-xs">Services will appear when telemetry is received</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full"
      style={{ minHeight: '300px', height: '100%' }}
    />
  );
}

export default CytoscapeGraph;
