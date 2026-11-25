// ui/src/components/approval/ApprovalResolvedSummary.tsx
// @ai-rules:
// 1. [Constraint]: Component must be <= 100 lines.
// 2. [Pattern]: Read-only frozen card showing chosen option or write-in summary.

import type { ApprovalResolution } from '../../api/types';

interface Props {
  resolution: ApprovalResolution;
}

export function ApprovalResolvedSummary({ resolution }: Props) {
  return (
    <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 6, background: '#1e293b', border: '1px solid #334155' }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4, display: 'flex', justifyContent: 'space-between' }}>
        <span>Resolved Decision</span>
        {resolution.resolved_by && <span>by {resolution.resolved_by}</span>}
      </div>
      <div style={{ fontSize: 14, color: '#f8fafc', fontWeight: 500 }}>
        {resolution.outcome === 'option' ? (
          <span>{resolution.option_label || resolution.option_id}</span>
        ) : resolution.outcome === 'write_in' ? (
          <span style={{ fontStyle: 'italic' }}>
            Write-in: {resolution.write_in_text ? `"${resolution.write_in_text}"` : 'Image instruction'}
          </span>
        ) : (
          <span style={{ color: '#94a3b8' }}>
            {resolution.outcome === 'closed' ? 'Closed' : resolution.outcome === 'superseded' ? 'Superseded' : resolution.outcome}
          </span>
        )}
      </div>
    </div>
  );
}
