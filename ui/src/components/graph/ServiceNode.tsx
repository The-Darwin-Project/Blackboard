// BlackBoard/ui/src/components/graph/ServiceNode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { GraphNode, HealthStatus, NodeType } from '../../api/types';

const HEALTH_COLORS: Record<HealthStatus, string> = {
  healthy: '#22c55e',
  warning: '#eab308',
  critical: '#ef4444',
  unknown: '#64748b',
};

const NODE_ICONS: Record<NodeType, string> = {
  service: '📦',
  database: '🛢️',
  cache: '⚡',
  external: '🌐',
};

type ServiceNodeData = GraphNode['metadata'] & {
  label: string;
  type: NodeType;
};

function ServiceNodeComponent({ data }: NodeProps & { data: ServiceNodeData }) {
  const health = data.health || 'unknown';
  const icon = NODE_ICONS[data.type] || '📦';
  const version = data.version || '?';
  const cpu = data.cpu?.toFixed(0) || '0';
  const mem = data.memory?.toFixed(0) || '0';
  const bg = HEALTH_COLORS[health];
  const textColor = health === 'warning' ? '#000' : '#fff';

  const gitopsRepo = data.gitops_repo;
  const gitopsPath = data.gitops_config_path || 'helm/values.yaml';

  const ready = data.replicas_ready;
  const desired = data.replicas_desired;

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div style={{
        position: 'relative',
        background: bg,
        borderRadius: 8,
        padding: '8px 12px',
        color: textColor,
        fontSize: 11,
        textAlign: 'center',
        width: 220,
        boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
      }}>
        {gitopsRepo && (
          <span
            title={`GitOps Config\nRepo: ${gitopsRepo}\nPath: ${gitopsPath}`}
            style={{ position: 'absolute', top: 4, right: 4, fontSize: 12, cursor: 'help', opacity: 0.9 }}
          >🔗</span>
        )}
        {desired != null && desired > 0 && (
          <span
            title={`Replicas: ${ready ?? 0} ready / ${desired} desired`}
            style={{
              position: 'absolute', top: 4, left: 4, fontSize: 9,
              background: 'rgba(0,0,0,0.4)', padding: '1px 5px', borderRadius: 4, cursor: 'help',
            }}
          >{ready ?? 0}/{desired}</span>
        )}
        <div style={{ fontSize: 16, marginBottom: 2 }}>{icon}</div>
        <div style={{
          fontWeight: 600, marginBottom: 2,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{data.label}</div>
        <div style={{ fontSize: 9, opacity: 0.9, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={`v${version}`}>
          v{version}
        </div>
        <div style={{ fontSize: 9, opacity: 0.8 }}>CPU:{cpu}% MEM:{mem}%</div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(ServiceNodeComponent);
