// BlackBoard/ui/src/components/Dashboard.tsx
/**
 * Main dashboard page with vertical stacked layout.
 * Top: CytoscapeGraph, Middle: MetricChart, Bottom: AgentFeed
 */
import { useState, useCallback } from 'react';
import CytoscapeGraph from './CytoscapeGraph';
import GraphContextMenu from './GraphContextMenu';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import AgentFeed from './AgentFeed';

interface ContextMenuState {
  serviceName: string;
  position: { x: number; y: number };
}

function Dashboard() {
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);

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

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-auto">
      {/* Top: Cytoscape Graph */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Architecture Graph</h2>
          <p className="text-xs text-text-muted">Service topology with health status</p>
        </div>
        <div className="h-[320px] overflow-hidden">
          <CytoscapeGraph 
            onNodeClick={handleNodeClick}
            onPlanClick={handlePlanClick}
          />
        </div>
      </div>

      {/* Middle: Metrics Chart */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Resource Consumption</h2>
          <p className="text-xs text-text-muted">CPU, Memory, Error Rate over time</p>
        </div>
        <div className="p-4">
          <MetricChart />
        </div>
      </div>

      {/* Bottom: Agent Feed */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col min-h-[200px]">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Agent Activity</h2>
          <p className="text-xs text-text-muted">Thought stream & plan management</p>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col">
          <AgentFeed />
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
