// BlackBoard/ui/src/components/ReportGrid.tsx
// @ai-rules:
// 1. [Pattern]: Tile design matches EventTicketCard -- full border ring, domain-colored.
// 2. [Constraint]: Cards show metadata only -- no markdown content loaded until selected.
// 3. [Pattern]: Severity badge uses inline SEVERITY_STYLES map (local, not shared).
/**
 * Responsive report tile grid for the Reports page State 1.
 * Displays persisted report metadata in a multi-column grid.
 */
import type { ReportMeta } from '../api/types';
import { DOMAIN_COLORS } from '../constants/colors';
import SourceIcon from './SourceIcon';

const SEVERITY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  info:     { bg: '#1e3a5f', text: '#7dd3fc', label: 'Info' },
  warning:  { bg: '#78350f', text: '#fcd34d', label: 'Warning' },
  critical: { bg: '#7f1d1d', text: '#fca5a5', label: 'Critical' },
};

interface ReportGridProps {
  reports: ReportMeta[];
  onSelectReport: (eventId: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortBy: 'date' | 'service';
  onSortChange: (sort: 'date' | 'service') => void;
}

export default function ReportGrid({
  reports, onSelectReport, searchQuery, onSearchChange, sortBy, onSortChange,
}: ReportGridProps) {
  const filtered = reports.filter((r) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return r.service.toLowerCase().includes(q)
      || r.event_id.toLowerCase().includes(q)
      || r.reason.toLowerCase().includes(q);
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'service') return a.service.localeCompare(b.service);
    return new Date(b.closed_at).getTime() - new Date(a.closed_at).getTime();
  });

  return (
    <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
      {/* Search + Sort */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search reports..."
          style={{
            flex: 1, background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: '8px 12px', color: '#e2e8f0', fontSize: 14,
          }}
        />
        <button
          onClick={() => onSortChange(sortBy === 'date' ? 'service' : 'date')}
          style={{
            background: '#334155', border: 'none', borderRadius: 6,
            color: '#94a3b8', padding: '8px 12px', cursor: 'pointer', fontSize: 12,
          }}
        >
          Sort: {sortBy === 'date' ? 'Newest' : 'Service'}
        </button>
      </div>

      {/* Tile Grid */}
      {sorted.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#64748b', fontSize: 14, padding: 40 }}>
          {searchQuery ? 'No reports match your search.' : 'No reports yet. Reports are generated when events close.'}
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: 14,
        }}>
          {sorted.map((report) => (
            <ReportTile key={report.event_id} report={report} onClick={() => onSelectReport(report.event_id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ReportTile({ report, onClick }: { report: ReportMeta; onClick: () => void }) {
  const domain = (report.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
  const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
  const severity = SEVERITY_STYLES[report.severity] || SEVERITY_STYLES.info;

  return (
    <div
      onClick={onClick}
      style={{
        padding: '16px 20px',
        borderRadius: 12,
        background: '#0f172a',
        border: `2px solid ${domainColor.border}88`,
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#1e293b';
        e.currentTarget.style.borderColor = domainColor.border;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#0f172a';
        e.currentTarget.style.borderColor = domainColor.border + '88';
      }}
    >
      {/* Header: source icon + service + badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <SourceIcon source={report.source} size={28} />
        <strong style={{ color: '#e2e8f0', fontSize: 16, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {report.service}
        </strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{
            background: severity.bg, color: severity.text,
            padding: '2px 10px', borderRadius: 10, fontSize: 11, fontWeight: 600,
          }}>
            {severity.label}
          </span>
          <span style={{
            background: domainColor.bg, color: domainColor.text,
            padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
            textTransform: 'uppercase',
          }}>
            {domain}
          </span>
        </div>
      </div>

      {/* Reason -- 3-line clamp for more detail */}
      <div style={{
        color: '#94a3b8', fontSize: 14, marginBottom: 10, lineHeight: 1.5,
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
      }} title={report.reason}>
        {report.reason}
      </div>

      {/* Footer: turns + date */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13, color: '#64748b' }}>
        <span>{report.turns} turns</span>
        <span>{new Date(report.closed_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>
      </div>

      {/* Event ID */}
      <div style={{ fontSize: 11, color: '#475569', marginTop: 6, fontFamily: 'monospace' }}>
        {report.event_id}
      </div>
    </div>
  );
}
