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
import { extractReasonDisplay } from './EventTicketCard';
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
  sortBy: 'date' | 'service' | 'domain' | 'severity';
  onSortChange: (sort: 'date' | 'service' | 'domain' | 'severity') => void;
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
    if (sortBy === 'domain') return a.domain.localeCompare(b.domain);
    if (sortBy === 'severity') {
      const order: Record<string, number> = { critical: 0, warning: 1, info: 2 };
      return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
    }
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          <span style={{ fontSize: 12, color: '#64748b', marginRight: 8 }}>Sort:</span>
          {([['date', 'Newest'], ['service', 'Service'], ['domain', 'Domain'], ['severity', 'Severity']] as const).map(([key, label], i, arr) => (
            <button
              key={key}
              onClick={() => onSortChange(key)}
              onMouseEnter={(e) => { if (sortBy !== key) e.currentTarget.style.background = '#334155'; }}
              onMouseLeave={(e) => { if (sortBy !== key) e.currentTarget.style.background = '#1e293b'; }}
              style={{
                background: sortBy === key ? '#3b82f6' : '#1e293b',
                border: sortBy === key ? '1px solid #60a5fa' : '1px solid #334155',
                borderLeft: i === 0 ? undefined : sortBy === key || sortBy === (['date', 'service', 'domain', 'severity'] as const)[i - 1] ? undefined : 'none',
                borderRadius: i === 0 ? '6px 0 0 6px' : i === arr.length - 1 ? '0 6px 6px 0' : 0,
                color: sortBy === key ? '#ffffff' : '#94a3b8',
                padding: '6px 14px', cursor: 'pointer', fontSize: 12, fontWeight: sortBy === key ? 600 : 400,
                transition: 'background 0.15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>
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
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      role="button"
      onMouseEnter={(e) => {
        e.currentTarget.style.background = '#1e293b';
        e.currentTarget.style.borderColor = domainColor.border;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = '#0f172a';
        e.currentTarget.style.borderColor = domainColor.border + '88';
      }}
      style={{
        padding: '16px 20px',
        borderRadius: 12,
        background: '#0f172a',
        border: `2px solid ${domainColor.border}88`,
        cursor: 'pointer',
        transition: 'all 0.15s',
        outline: 'none',
      }}
    >
      {/* Row 1: icon + severity + domain */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <SourceIcon source={report.source} size={28} />
        <span style={{
          background: severity.bg, color: severity.text,
          padding: '3px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600,
        }}>
          {severity.label}
        </span>
        <span style={{ flex: 1 }} />
        <span style={{
          background: domainColor.bg, color: domainColor.text,
          padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
          textTransform: 'uppercase',
        }}>
          {domain}
        </span>
      </div>

      {/* Row 2: service + timestamp */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, gap: 8 }}>
        <strong style={{ color: '#e2e8f0', fontSize: 15, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {report.service}
        </strong>
        <span style={{ fontSize: 12, color: '#64748b', flexShrink: 0 }}>
          {new Date(report.closed_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
        </span>
      </div>

      {/* Row 3: reason */}
      <div style={{
        color: '#94a3b8', fontSize: 13, lineHeight: 1.5,
        overflow: 'hidden', display: '-webkit-box',
        WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
        marginBottom: 8,
      }} title={report.reason}>
        {extractReasonDisplay(report.reason)}
      </div>

      {/* Footer: turns + event ID */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#475569' }}>
        <span>{report.turns} turns</span>
        <span style={{ fontFamily: 'monospace' }}>{report.event_id}</span>
      </div>
    </div>
  );
}
