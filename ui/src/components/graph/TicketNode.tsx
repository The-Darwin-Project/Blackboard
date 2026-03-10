// BlackBoard/ui/src/components/graph/TicketNode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

const TICKET_COLORS: Record<string, string> = {
  aligner: '#ef4444',
  chat: '#f59e0b',
  slack: '#8b5cf6',
  headhunter: '#06b6d4',
};

const STATUS_COLORS: Record<string, string> = {
  new: '#3b82f6',
  active: '#22c55e',
  deferred: '#a855f7',
  waiting_approval: '#eab308',
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
  const agent = data.current_agent || 'pending';
  const elapsed = data.elapsed_seconds < 60
    ? `${Math.round(data.elapsed_seconds)}s`
    : `${Math.round(data.elapsed_seconds / 60)}m`;
  const planIcon = data.has_work_plan ? '📋 ' : '';

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div style={{
        background: `${color}26`,
        border: `2px solid ${color}`,
        borderRadius: 8,
        padding: '6px 10px',
        color: color,
        fontSize: 11,
        textAlign: 'center',
        minWidth: 140,
      }}>
        <div style={{ fontSize: 14, marginBottom: 2 }}>🎫</div>
        <div style={{
          fontWeight: 600,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{planIcon}{data.event_id}</div>
        <div style={{ fontSize: 9, marginTop: 2 }}>
          <span style={{
            background: badgeColor, color: '#fff',
            padding: '1px 5px', borderRadius: 3,
          }}>{data.status}</span>
          <span style={{ opacity: 0.8, marginLeft: 4 }}>{agent}</span>
        </div>
        <div style={{ fontSize: 9, opacity: 0.7, marginTop: 2 }}>
          turns: {data.turn_count} &middot; {elapsed}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(TicketNodeComponent);
