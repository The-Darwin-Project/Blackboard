// BlackBoard/ui/src/components/ops/TopologyView.tsx
// @ai-rules:
// 1. [Pattern]: Sub-tabs [Graph | Resources]. Graph = ArchitectureGraph, Resources = MetricChart grid + inline NodeInspector.
// 2. [Pattern]: Multi-select up to 3 services from graph. Each gets enlarged chart. Pills in header for removal.
// 3. [Pattern]: NodeInspector renders inline in Resources tab (right panel), not a fixed overlay.
// 4. [Pattern]: Clicking a service card in Resources also toggles selection.
import { useState, useCallback } from 'react';
import ArchitectureGraph from '../graph/ArchitectureGraph';
import MetricChart from '../MetricChart';
import NodeInspector from '../NodeInspector';

const MAX_SELECTED = 3;

export default function TopologyView() {
  const [subTab, setSubTab] = useState<'graph' | 'resources'>('graph');
  const [selectedServices, setSelectedServices] = useState<string[]>([]);

  const toggleService = useCallback((name: string) => {
    setSelectedServices(prev => {
      if (prev.includes(name)) return prev.filter(s => s !== name);
      if (prev.length >= MAX_SELECTED) return [...prev.slice(1), name];
      return [...prev, name];
    });
    setSubTab('resources');
  }, []);

  const removeService = useCallback((name: string) => {
    setSelectedServices(prev => prev.filter(s => s !== name));
  }, []);

  const inspectedService = selectedServices.length > 0
    ? selectedServices[selectedServices.length - 1]
    : null;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-border flex-shrink-0">
        {(['graph', 'resources'] as const).map((tab) => (
          <button key={tab} onClick={() => setSubTab(tab)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              subTab === tab
                ? 'bg-accent/20 text-accent'
                : 'text-text-muted hover:text-text-secondary hover:bg-bg-tertiary'
            }`}>
            {tab === 'graph' ? 'Graph' : 'Resources'}
          </button>
        ))}
        {selectedServices.length > 0 && subTab === 'resources' && (
          <div className="flex items-center gap-1.5 ml-3">
            {selectedServices.map(svc => (
              <div key={svc} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 border border-accent/30 text-[11px] text-accent">
                {svc}
                <button onClick={() => removeService(svc)}
                  className="ml-0.5 hover:text-white transition-colors" title="Remove">&times;</button>
              </div>
            ))}
            {selectedServices.length > 1 && (
              <button onClick={() => setSelectedServices([])}
                className="text-[11px] text-text-muted hover:text-text-secondary ml-1"
                title="Clear all">clear</button>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <div style={{ display: subTab === 'graph' ? 'flex' : 'none', height: '100%', flexDirection: 'column' }}>
          <ArchitectureGraph
            onNodeClick={toggleService}
            onTicketClick={() => {}}
          />
        </div>
        <div style={{ display: subTab === 'resources' ? 'flex' : 'none', height: '100%' }}>
          <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
            <MetricChart highlightServices={selectedServices} onServiceClick={toggleService} />
          </div>
          {inspectedService && (
            <div style={{ width: 320, flexShrink: 0 }}>
              <NodeInspector
                serviceName={inspectedService}
                inline
                onClose={() => removeService(inspectedService)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
