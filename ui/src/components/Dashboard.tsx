// BlackBoard/ui/src/components/Dashboard.tsx
/**
 * Main dashboard page with 2-column layout.
 * Left: AgentFeed (Sidebar) - Resizable
 * Right: CytoscapeGraph (Top) + MetricChart (Bottom)
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import CytoscapeGraph from './CytoscapeGraph';
import GraphContextMenu from './GraphContextMenu';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import AgentFeed from './AgentFeed';

interface ContextMenuState {
  serviceName: string;
  position: { x: number; y: number };
}

// Resize constraints
const MIN_SIDEBAR_WIDTH = 280;
const MAX_SIDEBAR_WIDTH = 600;
const DEFAULT_SIDEBAR_WIDTH = 400;

function Dashboard() {
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle node click - open inspector
  const handleNodeClick = useCallback((serviceName: string) => {
    setSelectedService(serviceName);
    setSelectedPlan(null);
  }, []);

  // Handle plan (ghost node) click - open inspector in plan mode
  const handlePlanClick = useCallback((planId: string) => {
    setSelectedPlan(planId);
    setSelectedService(null);
  }, []);

  // Close context menu
  const handleCloseContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  // Resize handlers
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left - 16; // 16px for padding
      setSidebarWidth(Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, newWidth)));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  return (
    <div ref={containerRef} className="h-full flex p-4 overflow-hidden">
      {/* Left Column: Agent Activity (Sidebar) - Resizable */}
      <div 
        className="flex-shrink-0 bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col"
        style={{ width: sidebarWidth }}
      >
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Agent Activity</h2>
          <p className="text-xs text-text-muted">Thought stream & plan management</p>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <AgentFeed />
        </div>
      </div>

      {/* Resize Handle */}
      <div
        className={`w-4 flex-shrink-0 flex items-center justify-center cursor-col-resize group ${
          isResizing ? 'bg-accent/20' : ''
        }`}
        onMouseDown={startResize}
      >
        <div className={`w-1 h-16 rounded-full transition-colors ${
          isResizing ? 'bg-accent' : 'bg-border group-hover:bg-accent/60'
        }`} />
      </div>

      {/* Right Column: Graphs & Metrics */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Top: Architecture Graph */}
        <div className="flex-1 min-h-[300px] bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">Architecture Graph</h2>
            <p className="text-xs text-text-muted">Service topology with health status</p>
          </div>
          <div className="flex-1 overflow-hidden relative">
            <CytoscapeGraph 
              onNodeClick={handleNodeClick}
              onPlanClick={handlePlanClick}
            />
          </div>
        </div>

        {/* Bottom: Metrics Chart */}
        <div className="h-[320px] bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">Resource Consumption</h2>
            <p className="text-xs text-text-muted">CPU, Memory, Error Rate over time</p>
          </div>
          <div className="flex-1 p-4 overflow-hidden">
            <MetricChart />
          </div>
        </div>
      </div>

      {/* Node Inspector Drawer */}
      <NodeInspector
        serviceName={selectedService}
        planId={selectedPlan}
        onClose={() => {
          setSelectedService(null);
          setSelectedPlan(null);
        }}
      />

      {/* Context Menu */}
      {contextMenu && (
        <GraphContextMenu
          serviceName={contextMenu.serviceName}
          position={contextMenu.position}
          onClose={handleCloseContextMenu}
        />
      )}
    </div>
  );
}

export default Dashboard;
