// BlackBoard/ui/src/components/Dashboard.tsx
/**
 * Main dashboard page with 3-pane layout.
 * Left: TopologyViewer, Center: MetricChart, Right: AgentFeed
 */
import { useState } from 'react';
import TopologyViewer from './TopologyViewer';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import AgentFeed from './AgentFeed';

function Dashboard() {
  const [selectedService, setSelectedService] = useState<string | null>(null);

  return (
    <div className="h-full grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 overflow-hidden">
      {/* Left Pane: Topology Viewer */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Architecture Graph</h2>
          <p className="text-xs text-text-muted">Service topology with status</p>
        </div>
        <div className="flex-1 overflow-hidden">
          <TopologyViewer onNodeClick={setSelectedService} />
        </div>
      </div>

      {/* Center Pane: Metrics Chart */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Resource Consumption</h2>
          <p className="text-xs text-text-muted">CPU, Memory, Error Rate over time</p>
        </div>
        <div className="flex-1 overflow-hidden p-4">
          <MetricChart />
        </div>
      </div>

      {/* Right Pane: Agent Feed */}
      <div className="bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
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
