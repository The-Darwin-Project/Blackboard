// BlackBoard/ui/src/components/CytoscapeGraph.tsx
/**
 * Cytoscape.js-based architecture graph visualization.
 * 
 * Features:
 * - Health-based node colors (green/yellow/red/grey)
 * - Node type icons (service/database/cache/external)
 * - Ghost nodes for pending plans
 * - cose-bilkent auto-layout
 * - Navigation controls (zoom in/out/reset, pan)
 * - View state persistence in localStorage
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import nodeHtmlLabel from 'cytoscape-node-html-label';
import { Loader2, Network, ZoomIn, ZoomOut, RotateCcw, Maximize2 } from 'lucide-react';
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

// LocalStorage key for view state persistence
const VIEW_STATE_KEY = 'darwin:graph:view';

interface ViewState {
  zoom: number;
  pan: { x: number; y: number };
}

interface CytoscapeGraphProps {
  onNodeClick?: (serviceName: string) => void;
  onPlanClick?: (planId: string) => void;
}

function CytoscapeGraph({ onNodeClick, onPlanClick }: CytoscapeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cyRef = useRef<any>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [hasUserInteracted, setHasUserInteracted] = useState(false);
  const { data, isLoading, isError } = useGraph();

  // Debug: Log render state
  console.log('[CytoscapeGraph] Render state:', {
    isLoading,
    isError,
    hasData: !!data,
    nodeCount: data?.nodes?.length ?? 0,
    edgeCount: data?.edges?.length ?? 0,
    isInitialized,
    hasContainer: !!containerRef.current,
  });

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

  // Load view state from localStorage
  const loadViewState = useCallback((): ViewState | null => {
    try {
      const stored = localStorage.getItem(VIEW_STATE_KEY);
      if (stored) {
        return JSON.parse(stored) as ViewState;
      }
    } catch (err) {
      console.warn('[CytoscapeGraph] Failed to load view state:', err);
    }
    return null;
  }, []);

  // Save view state to localStorage
  const saveViewState = useCallback((cy: any) => {
    try {
      const zoom = cy.zoom();
      const pan = cy.pan();
      const viewState: ViewState = { zoom, pan };
      localStorage.setItem(VIEW_STATE_KEY, JSON.stringify(viewState));
    } catch (err) {
      console.warn('[CytoscapeGraph] Failed to save view state:', err);
    }
  }, []);

  // Navigation controls
  const handleZoomIn = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * 1.2, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
    saveViewState(cy);
    setHasUserInteracted(true);
  }, [saveViewState]);

  const handleZoomOut = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * 0.8, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
    saveViewState(cy);
    setHasUserInteracted(true);
  }, [saveViewState]);

  const handleReset = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.fit(undefined, 30);
    saveViewState(cy);
    setHasUserInteracted(true);
  }, [saveViewState]);

  const handleFit = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.fit(undefined, 30);
    saveViewState(cy);
    setHasUserInteracted(true);
  }, [saveViewState]);

  // Initialize Cytoscape (when we have data and container is mounted)
  // This effect runs when data changes - container is only rendered when data.nodes.length > 0
  useEffect(() => {
    // Skip if no data or already initialized
    if (!data?.nodes?.length || cyRef.current) return;
    
    // Container should exist now since we're past the loading/empty states
    const container = containerRef.current;
    if (!container) {
      console.log('[CytoscapeGraph] Container not yet available, waiting...');
      return;
    }

    const rect = container.getBoundingClientRect();
    console.log('[CytoscapeGraph] Initializing Cytoscape with dimensions:', { width: rect.width, height: rect.height });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const cy = (cytoscape as any)({
      container: container,
      style: [
        // Base node style (fallback if HTML labels fail)
        {
          selector: 'node',
          style: {
            'width': 100,
            'height': 70,
            'shape': 'round-rectangle',
            'background-color': '#64748b',
            'background-opacity': 1,
            'label': 'data(label)',
            'color': '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': 10,
          },
        },
        // Health-based colors for fallback
        {
          selector: 'node[health="healthy"]',
          style: {
            'background-color': '#22c55e',
          },
        },
        {
          selector: 'node[health="warning"]',
          style: {
            'background-color': '#eab308',
            'color': '#000',
          },
        },
        {
          selector: 'node[health="critical"]',
          style: {
            'background-color': '#ef4444',
          },
        },
        // Ghost node style
        {
          selector: 'node.ghost',
          style: {
            'width': 90,
            'height': 60,
            'background-color': '#6366f1',
            'background-opacity': 0.1,
            'border-width': 2,
            'border-style': 'dashed',
            'border-color': '#6366f1',
            'label': 'data(label)',
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
    console.log('[CytoscapeGraph] Cytoscape initialized successfully');

    // Save view state on pan/zoom
    const handlePanZoom = () => {
      saveViewState(cy);
      setHasUserInteracted(true);
    };
    cy.on('pan', handlePanZoom);
    cy.on('zoom', handlePanZoom);

    return () => {
      cy.off('pan', handlePanZoom);
      cy.off('zoom', handlePanZoom);
      // Clean up HTML labels before destroying Cytoscape
      cleanupHtmlLabels();
      cy.destroy();
      cyRef.current = null;
      setIsInitialized(false);
      setHasUserInteracted(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.nodes?.length, saveViewState]);

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

    console.log('[CytoscapeGraph] Updating graph with data:', data);

    // Save current view state before update (if user has interacted)
    const previousViewState = hasUserInteracted ? {
      zoom: cy.zoom(),
      pan: cy.pan(),
    } : null;

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

    console.log('[CytoscapeGraph] Constructed elements:', elements);

    // Clean up existing HTML labels before removing elements (prevents memory leaks)
    cleanupHtmlLabels();
    
    // Update graph
    cy.elements().remove();
    cy.add(elements);
    console.log('[CytoscapeGraph] Elements added to graph');

    // Apply HTML labels if extension is available
    if (typeof cy.nodeHtmlLabel === 'function') {
      try {
        console.log('[CytoscapeGraph] Configuring nodeHtmlLabel...');
        // Register HTML labels
        cy.nodeHtmlLabel([
          {
            query: 'node:not(.ghost)',
            halign: 'center',
            valign: 'center',
            halignBox: 'center',
            valignBox: 'center',
            tpl: (nodeData: unknown) => {
              console.log('[CytoscapeGraph] Generating HTML label for node:', nodeData);
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

        // IMPORTANT: Only hide the default node body IF we are sure the HTML label extension is active.
        // We can't easily detect if it "worked" per node, but if we got here, the extension is registered.
        // However, if the user sees transparent nodes, it means this code ran but the HTML didn't render.
        // Let's keep the fallback visible for now to debug, or try to force a redraw.
        
        // Strategy: We will NOT hide the node body completely yet. 
        // Instead, we'll make it transparent ONLY if we are confident.
        // For now, let's leave the fallback visible underneath (or behind) the HTML label
        // so if the HTML label fails, the user sees the node.
        // But if the HTML label works, it covers the node.
        
        // To do this, we need the HTML label to be opaque (it is) and centered (it is).
        // So we can remove the code that hides the node body.
        
        /* 
        cy.style()
          .selector('node')
          .style({
            'background-opacity': 0,
            'label': '',
            'border-width': 0,
          })
          .update();
        */
          
      } catch (err) {
        console.error('[CytoscapeGraph] Failed to apply HTML labels:', err);
      }
    } else {
      console.warn('[CytoscapeGraph] nodeHtmlLabel extension not available');
    }

    // Run layout
    try {
      cy.layout(LAYOUT_OPTIONS).run();
    } catch (err) {
      console.error('[CytoscapeGraph] Layout failed:', err);
      // Fallback to basic grid layout
      cy.layout({ name: 'grid' }).run();
    }

    // Restore view state: preserve user's view if they've interacted, otherwise fit to viewport
    const savedViewState = loadViewState();
    if (previousViewState) {
      // User has interacted: restore their previous view state
      cy.zoom(previousViewState.zoom);
      cy.pan(previousViewState.pan);
      console.log('[CytoscapeGraph] Restored previous view state (zoom:', previousViewState.zoom, ')');
    } else if (savedViewState) {
      // No current interaction but we have saved state: restore from localStorage
      cy.zoom(savedViewState.zoom);
      cy.pan(savedViewState.pan);
      console.log('[CytoscapeGraph] Restored saved view state from localStorage');
    } else {
      // First load: fit to viewport with padding
      cy.fit(undefined, 30);
      saveViewState(cy);
      console.log('[CytoscapeGraph] Fitted to viewport (initial load)');
    }

    // Debug: Log final state
    console.log('[CytoscapeGraph] Graph updated. Nodes:', cy.nodes().length, 'Edges:', cy.edges().length);
    cy.nodes().forEach((node: any) => {
      const pos = node.position();
      console.log('[CytoscapeGraph] Node position:', node.id(), pos);
    });

  }, [data, isInitialized, buildNodeLabel, buildGhostLabel, cleanupHtmlLabels, hasUserInteracted, loadViewState, saveViewState]);

  if (isLoading) {
    console.log('[CytoscapeGraph] Rendering: LOADING');
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-accent animate-spin" />
      </div>
    );
  }

  if (isError) {
    console.log('[CytoscapeGraph] Rendering: ERROR');
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <Network className="w-12 h-12" />
        <p className="text-sm">Unable to load graph</p>
        <p className="text-xs">Check API connection</p>
      </div>
    );
  }

  if (!data?.nodes.length) {
    console.log('[CytoscapeGraph] Rendering: NO NODES');
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <Network className="w-12 h-12" />
        <p className="text-sm">No services registered</p>
        <p className="text-xs">Services will appear when telemetry is received</p>
      </div>
    );
  }

  console.log('[CytoscapeGraph] Rendering: CONTAINER (nodes:', data.nodes.length, ')');
  return (
    <div className="relative w-full h-full" style={{ minHeight: '300px', height: '100%' }}>
      {/* Graph Container */}
      <div
        ref={containerRef}
        className="w-full h-full"
      />
      
      {/* Navigation Controls */}
      <div className="absolute top-4 right-4 flex flex-col gap-2 bg-bg-secondary/90 backdrop-blur-sm border border-border rounded-lg p-2 shadow-lg">
        <button
          onClick={handleZoomIn}
          className="p-2 hover:bg-bg-hover rounded transition-colors"
          title="Zoom In"
          aria-label="Zoom In"
        >
          <ZoomIn className="w-4 h-4 text-text-primary" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 hover:bg-bg-hover rounded transition-colors"
          title="Zoom Out"
          aria-label="Zoom Out"
        >
          <ZoomOut className="w-4 h-4 text-text-primary" />
        </button>
        <div className="h-px bg-border my-1" />
        <button
          onClick={handleFit}
          className="p-2 hover:bg-bg-hover rounded transition-colors"
          title="Fit to View"
          aria-label="Fit to View"
        >
          <Maximize2 className="w-4 h-4 text-text-primary" />
        </button>
        <button
          onClick={handleReset}
          className="p-2 hover:bg-bg-hover rounded transition-colors"
          title="Reset View"
          aria-label="Reset View"
        >
          <RotateCcw className="w-4 h-4 text-text-primary" />
        </button>
      </div>
    </div>
  );
}

export default CytoscapeGraph;
