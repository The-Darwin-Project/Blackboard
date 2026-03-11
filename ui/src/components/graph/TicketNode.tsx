// BlackBoard/ui/src/components/graph/TicketNode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import './ArchitectureGraph.css';

const TICKET_COLORS: Record<string, string> = {
  aligner: '#ef4444', chat: '#f59e0b', slack: '#8b5cf6', headhunter: '#06b6d4',
};

const STATUS_COLORS: Record<string, string> = {
  new: '#3b82f6', active: '#22c55e', deferred: '#a855f7', waiting_approval: '#eab308',
};

interface TicketNodeData {
  event_id: string;
  status: string;
  source: string;
  turn_count: number;
  elapsed_seconds: number;
  current_agent: string | null;
  has_work_plan: boolean;
}

function TicketNodeComponent({ data }: NodeProps & { data: TicketNodeData }) {
  const color = TICKET_COLORS[data.source] || '#f59e0b';
  const badgeColor = STATUS_COLORS[data.status] || '#64748b';
  const elapsed = data.elapsed_seconds < 60
    ? `${Math.round(data.elapsed_seconds)}s`
    : `${Math.round(data.elapsed_seconds / 60)}m`;

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="ticket-node" style={{ borderLeft: `3px solid ${color}`, color }}>
        <div className="ticket-node-header">
          {data.has_work_plan && <span>📋</span>}
          <span className="ticket-node-id">{data.event_id}</span>
        </div>

        <span className="ticket-node-status" style={{ background: badgeColor }}>
          {data.status}
        </span>

        <div className="ticket-node-agent">
          {data.current_agent || 'pending'}
        </div>

        <div className="ticket-node-detail">
          turns: {data.turn_count} &middot; {elapsed}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(TicketNodeComponent);
