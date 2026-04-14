// BlackBoard/ui/src/components/ReportHeader.tsx
// @ai-rules:
// 1. [Pattern]: Built from ReportFull structured metadata -- no markdown parsing.
// 2. [Constraint]: Pure display component. Reuses DOMAIN_COLORS, SEVERITY_COLORS, SourceIcon.
import type { ReportFull } from '../api/types';
import { DOMAIN_COLORS, SEVERITY_COLORS } from '../constants/colors';
import SourceIcon from './SourceIcon';

export default function ReportHeader({ report }: { report: ReportFull }) {
  const domain = (report.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
  const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
  const severity = SEVERITY_COLORS[report.severity] || SEVERITY_COLORS.info;

  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: 10,
      padding: '12px 14px',
      background: '#0f172a',
      borderRadius: 8,
      border: `1px solid ${domainColor.border}44`,
      marginBottom: 12,
    }}>
      <SourceIcon source={report.source} subjectType={report.subject_type} size={28} />

      <div style={{ flex: 1, minWidth: 160 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>
          {report.service}
        </div>
        <div style={{
          fontSize: 12,
          color: '#64748b',
          fontFamily: 'monospace',
          marginTop: 2,
        }}>
          {report.event_id}
        </div>
      </div>

      <span style={{
        background: severity.bg,
        color: severity.text,
        padding: '3px 12px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
      }}>
        {severity.label}
      </span>

      <span style={{
        background: domainColor.bg,
        color: domainColor.text,
        padding: '3px 10px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'uppercase',
      }}>
        {domain}
      </span>

      <span style={{ fontSize: 12, color: '#64748b' }}>
        {report.turns} turns
      </span>

      <span style={{ fontSize: 12, color: '#64748b' }}>
        {new Date(report.closed_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
      </span>
    </div>
  );
}
