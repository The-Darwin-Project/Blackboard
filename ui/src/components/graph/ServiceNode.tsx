// BlackBoard/ui/src/components/graph/ServiceNode.tsx
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { HealthStatus, NodeType } from '../../api/types';
import './ArchitectureGraph.css';

const HEALTH_COLORS: Record<HealthStatus, string> = {
  healthy: '#22c55e',
  warning: '#eab308',
  critical: '#ef4444',
  unknown: '#6b7280',
};

const NODE_ICONS: Record<NodeType, string> = {
  service: '📦', database: '🛢️', cache: '⚡', external: '🌐',
};

interface ServiceNodeData {
  label: string;
  type: NodeType;
  health: HealthStatus;
  version: string;
  cpu: number;
  memory: number;
  gitops_repo?: string;
  gitops_config_path?: string;
  replicas_ready?: number;
  replicas_desired?: number;
}

const GENERIC_TAGS = new Set(['k8s', 'latest', 'unknown', '?', '']);

function ServiceNodeComponent({ data }: NodeProps & { data: ServiceNodeData }) {
  const health = data.health || 'unknown';
  const healthColor = HEALTH_COLORS[health];
  const icon = NODE_ICONS[data.type] || '📦';
  const cpu = data.cpu?.toFixed(0) || '0';
  const mem = data.memory?.toFixed(0) || '0';
  const ready = data.replicas_ready;
  const desired = data.replicas_desired;
  const version = data.version || '?';
  const isGenericTag = GENERIC_TAGS.has(version.toLowerCase());

  const stateClass = health === 'critical' ? ' service-node-critical'
    : health === 'warning' ? ' service-node-warning' : '';

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className={`service-node${stateClass}`}>
        <div className="service-node-header">
          <span className="service-node-health" style={{ backgroundColor: healthColor }} title={health} />
          <span className="service-node-name">{data.label}</span>
          <span className="service-node-icon">{icon}</span>
        </div>

        <div className="service-node-metrics">
          <span>CPU: {cpu}%</span>
          <span>MEM: {mem}%</span>
        </div>

        <div className="service-node-meta">
          {!isGenericTag && (
            <span className="service-node-badge" title={version}>
              {version}
            </span>
          )}
          {isGenericTag && (
            <span className="service-node-badge service-node-badge-source" title={`Platform: ${version}`}>
              {version}
            </span>
          )}
          {desired != null && desired > 0 && (
            <span className="service-node-badge" title={`${ready ?? 0} ready / ${desired} desired`}>
              {ready ?? 0}/{desired}
            </span>
          )}
          {data.gitops_repo && (
            <span className="service-node-badge service-node-badge-gitops" title={`GitOps: ${data.gitops_repo}`}>
              🔗 GitOps
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(ServiceNodeComponent);
