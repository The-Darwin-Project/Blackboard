// BlackBoard/ui/src/components/ops/TopologyView.tsx
// @ai-rules:
// 1. [Pattern]: Sub-tabs [Graph | Resources]. Graph = ArchitectureGraph, Resources = MetricChart grid.
// 2. [Pattern]: Node click -> "View Metrics" switches to Resources filtered to that service.
// 3. [Constraint]: Step 1 placeholder -- full implementation in Step 4a.
import { useState } from 'react';
import ArchitectureGraph from '../graph/ArchitectureGraph';
import MetricChart from '../MetricChart';
import NodeInspector from '../NodeInspector';

export default function TopologyView() {
  const [subTab, setSubTab] = useState<'graph' | 'resources'>('graph');
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [filteredService, setFilteredService] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-border flex-shrink-0">
        {(['graph', 'resources'] as const).map((tab) => (
          <button key={tab} onClick={() => { setSubTab(tab); if (tab === 'graph') setFilteredService(null); }}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              subTab === tab
                ? 'bg-accent/20 text-accent'
                : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
            }`}>
            {tab === 'graph' ? 'Graph' : 'Resources'}
          </button>
        ))}
        {filteredService && subTab === 'resources' && (
          <div className="flex items-center gap-1.5 ml-3 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/30 text-[11px] text-accent">
            {filteredService}
            <button onClick={() => setFilteredService(null)}
              className="ml-0.5 hover:text-white transition-colors" title="Clear filter">&times;</button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        <div style={{ display: subTab === 'graph' ? 'flex' : 'none', height: '100%', flexDirection: 'column' }}>
          <ArchitectureGraph
            onNodeClick={(name) => {
              setSelectedService(name);
              setFilteredService(name);
              setSubTab('resources');
            }}
            onTicketClick={() => {}}
          />
        </div>
        <div style={{ display: subTab === 'resources' ? 'block' : 'none', height: '100%', overflow: 'auto', padding: 16 }}>
          <MetricChart highlightService={filteredService} />
        </div>
      </div>

      <NodeInspector
        serviceName={selectedService}
        onClose={() => setSelectedService(null)}
      />
    </div>
  );
}
