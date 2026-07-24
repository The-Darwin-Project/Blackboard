// BlackBoard/ui/src/components/graph/AppNode.tsx
// @ai-rules:
// 1. [Pattern]: Config-only ArgoCD Application node — no replicas, no version, no escalation badge.
// 2. [Pattern]: Namespace-grouped via parentId (same as ServiceNode).
// 3. [Constraint]: Inline SVG only (consistent with SourceIcon @ai-shebang).
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { ARGOCD_HEALTH_COLORS, SYNC_ICONS } from './constants';
import './ArchitectureGraph.css';

interface AppNodeData {
  name: string;
  health: string;
  sync_status: string;
  namespace: string;
  argocd_app: string;
}

function AppNodeComponent({ data }: NodeProps & { data: AppNodeData }) {
  const healthColor = ARGOCD_HEALTH_COLORS[data.health] || ARGOCD_HEALTH_COLORS.Unknown;
  const syncIcon = data.sync_status ? SYNC_ICONS[data.sync_status] : undefined;

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="service-node" style={{ borderColor: '#EF7B4D33', minWidth: 180 }}>
        <div className="service-node-header">
          <span
            className="service-node-health"
            style={{ backgroundColor: healthColor }}
            title={data.health}
          />
          <span className="service-node-name">{data.name}</span>
          <img src="/argocd.png" width={18} height={18} alt="ArgoCD" style={{ flexShrink: 0, borderRadius: 3 }} />
        </div>

        <div className="service-node-status-row">
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
          <span className="service-node-badge" title="Config-only (no workloads)" style={{ color: '#EF7B4D', borderColor: '#EF7B4D55' }}>
            config-only
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export default memo(AppNodeComponent);
