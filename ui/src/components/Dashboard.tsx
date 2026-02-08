// BlackBoard/ui/src/components/Dashboard.tsx
/**
 * Main dashboard page with 2-column layout.
 * Left: ConversationFeed (Sidebar) - Resizable
 * Right: CytoscapeGraph (Top) + MetricChart (Bottom)
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import CytoscapeGraph from './CytoscapeGraph';
import GraphContextMenu from './GraphContextMenu';
import NodeInspector from './NodeInspector';
import MetricChart from './MetricChart';
import ConversationFeed from './ConversationFeed';
import AgentStreamCard from './AgentStreamCard';
import { WebSocketProvider, useWSMessage } from '../contexts/WebSocketContext';

interface ContextMenuState {
  serviceName: string;
  position: { x: number; y: number };
}

// Resize constraints
const MIN_SIDEBAR_WIDTH = 280;
const MAX_SIDEBAR_WIDTH = 600;
const DEFAULT_SIDEBAR_WIDTH = 400;

// Agent stream state -- per-agent message buffers
interface AgentStreamState {
  messages: string[];
  eventId: string | null;
  isActive: boolean;
}

const AGENTS = ['architect', 'sysadmin', 'developer'] as const;
const MAX_BUFFER = 100;

function DashboardInner() {
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_SIDEBAR_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Agent streaming card state
  const [agentStreams, setAgentStreams] = useState<Record<string, AgentStreamState>>(() => {
    const init: Record<string, AgentStreamState> = {};
    for (const a of AGENTS) init[a] = { messages: [], eventId: null, isActive: false };
    return init;
  });

  // Route WS messages to agent stream cards
  useWSMessage((msg) => {
    if (msg.type === 'progress' && msg.actor && AGENTS.includes(msg.actor as typeof AGENTS[number])) {
      setAgentStreams((prev) => {
        const agent = msg.actor as string;
        const current = prev[agent] || { messages: [], eventId: null, isActive: false };
        const messages = [...current.messages, msg.message as string].slice(-MAX_BUFFER);
        return { ...prev, [agent]: { messages, eventId: (msg.event_id as string) || current.eventId, isActive: true } };
      });
    } else if (msg.type === 'turn') {
      const turn = msg.turn as Record<string, unknown>;
      const actor = turn?.actor as string;
      if (actor && AGENTS.includes(actor as typeof AGENTS[number])) {
        setAgentStreams((prev) => ({
          ...prev,
          [actor]: { ...prev[actor], isActive: false },
        }));
      }
    }
  });

  // Handle node click - open inspector
  const handleNodeClick = useCallback((serviceName: string) => {
    setSelectedService(serviceName);
  }, []);

  // Handle plan (ghost node) click - open inspector in plan mode
  const handlePlanClick = useCallback((_planId: string) => {
    // Plan ghost nodes are no longer used; no-op for now
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
        className="flex-shrink-0 h-full bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col"
        style={{ width: sidebarWidth }}
      >
        <div className="flex-shrink-0 px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text-primary">Agent Activity</h2>
          <p className="text-xs text-text-muted">Thought stream & plan management</p>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <ConversationFeed />
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

      {/* Right Column: Agent Streams + Graphs + Metrics */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        {/* Top: Agent Streaming Cards */}
        <div className="flex gap-3 flex-shrink-0" style={{ height: 220 }}>
          {AGENTS.map((agent) => (
            <AgentStreamCard
              key={agent}
              agentName={agent}
              eventId={agentStreams[agent]?.eventId || null}
              messages={agentStreams[agent]?.messages || []}
              isActive={agentStreams[agent]?.isActive || false}
            />
          ))}
        </div>

        {/* Middle: Architecture Graph */}
        <div className="flex-1 min-h-[250px] bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
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
        <div className="h-[280px] bg-bg-secondary rounded-lg border border-border overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">Resource Consumption</h2>
            <p className="text-xs text-text-muted">CPU, Memory, Error Rate over time</p>
          </div>
          <div className="flex-1 p-4 overflow-auto">
            <MetricChart />
          </div>
        </div>
      </div>

      {/* Node Inspector Drawer */}
      <NodeInspector
        serviceName={selectedService}
        onClose={() => {
          setSelectedService(null);
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

/** Wrapper that provides WebSocket context to DashboardInner + children. */
function Dashboard() {
  return (
    <WebSocketProvider>
      <DashboardInner />
    </WebSocketProvider>
  );
}

export default Dashboard;
