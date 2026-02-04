// BlackBoard/ui/src/components/Dashboard.tsx
/**
 * Main dashboard page with vertical stacked layout.
 * Top: TopologyViewer, Middle: MetricChart, Bottom: AgentFeed
 */
import { useState } from 'react';
import TopologyViewer from './TopologyViewer';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import AgentFeed from './AgentFeed';

function Dashboard() {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-auto">
      {/* Top: Topology Viewer */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Architecture Graph</h2>
          <p className="text-xs text-text-muted">Service topology with status</p>
        </div>
        <div className="h-[280px] overflow-hidden">
          <TopologyViewer onNodeClick={setSelectedService} />
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
        onClose={() => setSelectedService(null)}
      />
    </div>
  );
}

export default Dashboard;
