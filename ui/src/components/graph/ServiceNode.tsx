// BlackBoard/ui/src/components/graph/ServiceNode.tsx
// @ai-rules:
// 1. [Pattern]: Health dot color prefers the raw ArgoCD health_status (4-state: Healthy/
//    Progressing/Degraded/Missing-Unknown) over the collapsed traffic-light `health` field,
//    EXCEPT when health === 'unknown' (zombie/no-data) which always wins -- a stale
//    health_status string must never paint a disconnected service green.
// 2. [Pattern]: Sync badge only renders for a known ArgoCD sync_status (Synced/OutOfSync).
// 3. [Gotcha]: Anchor tags (source repo link) call stopPropagation so clicking them doesn't
//    also trigger the ReactFlow onNodeClick node-selection handler.
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

const ARGOCD_HEALTH_COLORS: Record<string, string> = {
  Healthy: '#22c55e',
  Progressing: '#eab308',
  Degraded: '#ef4444',
  Missing: '#6b7280',
  Unknown: '#6b7280',
};

const SYNC_ICONS: Record<string, string> = {
  Synced: '\u2713',
  OutOfSync: '\u26a0',
};

const NODE_ICONS: Record<NodeType, string> = {
  service: '📦', database: '🛢️', cache: '⚡', external: '🌐',
};

interface ServiceNodeData {
  label: string;
  type: NodeType;
  health: HealthStatus;
  health_status?: string | null;
  sync_status?: string | null;
  version: string;
  namespace?: string | null;
  source_repo_url?: string | null;
  gitops_repo?: string;
  gitops_repo_url?: string;
  gitops_config_path?: string;
  replicas_ready?: number;
  replicas_desired?: number;
  escalation_flag?: string;
  icon?: string;
}

const GENERIC_TAGS = new Set(['k8s', 'latest', 'unknown', '?', '']);

function resolveHealthColor(health: HealthStatus, healthStatus?: string | null): string {
  if (health === 'unknown') return HEALTH_COLORS.unknown;
  if (healthStatus && ARGOCD_HEALTH_COLORS[healthStatus]) return ARGOCD_HEALTH_COLORS[healthStatus];
  return HEALTH_COLORS[health];
}

function ServiceNodeComponent({ data }: NodeProps & { data: ServiceNodeData }) {
  const health = data.health || 'unknown';
  const healthColor = resolveHealthColor(health, data.health_status);
  const icon = data.icon || NODE_ICONS[data.type] || '📦';
  const ready = data.replicas_ready;
  const desired = data.replicas_desired;
  const version = data.version || '?';
  const isGenericTag = GENERIC_TAGS.has(version.toLowerCase());
  const sourceUrl = data.gitops_repo_url || data.source_repo_url;
  const syncIcon = data.sync_status ? SYNC_ICONS[data.sync_status] : undefined;

  const stateClass = health === 'critical' ? ' service-node-critical'
    : health === 'warning' ? ' service-node-warning' : '';

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className={`service-node${stateClass}`}>
        <div className="service-node-header">
          <span
            className="service-node-health"
            style={{ backgroundColor: healthColor }}
            title={data.health_status || health}
          />
          <span className="service-node-name">{data.label}</span>
          <span className="service-node-icon">{icon}</span>
        </div>

        <div className="service-node-status-row">
          {data.namespace && (
            <span className="service-node-namespace" title={`Namespace: ${data.namespace}`}>
              {data.namespace}
            </span>
          )}
          {syncIcon && (
            <span
              className={`service-node-sync service-node-sync-${data.sync_status?.toLowerCase()}`}
              title={`Sync: ${data.sync_status}`}
            >
              {syncIcon} {data.sync_status}
            </span>
          )}
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
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="service-node-badge service-node-badge-gitops"
              title={`Source: ${sourceUrl}`}
              onClick={(e) => e.stopPropagation()}
            >
              🔗 Source
            </a>
          )}
          {data.escalation_flag && (
            <span className="service-node-badge service-node-badge-escalated" title={data.escalation_flag}>
              ESCALATED
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(ServiceNodeComponent);
