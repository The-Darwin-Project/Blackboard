// BlackBoard/ui/src/components/EventHistoryGrid.tsx
// @ai-rules:
// 1. [Pattern]: Card layout extracted from ReportGrid.tsx. Same tile design, different data source.
// 2. [Constraint]: No search/sort UI here -- that lives in EventHistoryToolbar.
// 3. [Pattern]: Uses shared DOMAIN_COLORS, SEVERITY_COLORS, SourceIcon.
import type { ReportMeta } from '../api/types';
import { extractReasonDisplay, resolveSubjectType } from '../utils/eventFormat';
import { DOMAIN_COLORS, SEVERITY_COLORS } from '../constants/colors';
import SourceIcon from './SourceIcon';

interface Props {
  reports: ReportMeta[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function EventHistoryGrid({ reports, selectedId, onSelect }: Props) {
  if (reports.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm p-10">
        No events match your filters.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-4">
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 14,
      }}>
        {reports.map((report) => (
          <GridTile
            key={report.event_id}
            report={report}
            isSelected={report.event_id === selectedId}
            onClick={() => onSelect(report.event_id)}
          />
        ))}
      </div>
    </div>
  );
}

function GridTile({ report, isSelected, onClick }: {
  report: ReportMeta; isSelected: boolean; onClick: () => void;
}) {
  const domain = (report.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
  const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
  const severity = SEVERITY_COLORS[report.severity] || SEVERITY_COLORS.info;

  return (
    <div
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      role="button"
      className={`rounded-xl cursor-pointer transition-all outline-none ${isSelected ? 'ring-2 ring-accent' : ''}`}
      style={{
        padding: '16px 20px',
        background: isSelected ? '#1e293b' : '#0f172a',
        border: `2px solid ${domainColor.border}${isSelected ? '' : '88'}`,
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <SourceIcon source={report.source} subjectType={resolveSubjectType(report.subject_type, report.service)} size={28} />
        <span style={{ background: severity.bg, color: severity.text, padding: '3px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>
          {severity.label}
        </span>
        <span className="flex-1" />
        <span style={{ background: domainColor.bg, color: domainColor.text, padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, textTransform: 'uppercase' }}>
          {domain}
        </span>
      </div>

      <div className="flex justify-between items-center mb-2 gap-2">
        <strong className="text-text-primary text-[15px] truncate">{report.service}</strong>
        <span className="text-xs text-text-muted flex-shrink-0">
          {new Date(report.closed_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
        </span>
      </div>

      <div className="text-text-secondary text-[13px] leading-relaxed mb-2 line-clamp-3" title={report.reason}>
        {extractReasonDisplay(report.reason)}
      </div>

      <div className="flex justify-between items-center text-[11px] text-text-muted">
        <span>{report.turns} turns{report.triggered_by ? ` · ${report.triggered_by}` : ''}</span>
        <span className="font-mono">{report.event_id}</span>
      </div>
    </div>
  );
}
