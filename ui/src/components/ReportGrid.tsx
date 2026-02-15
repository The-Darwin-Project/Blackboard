// BlackBoard/ui/src/components/ReportGrid.tsx
// @ai-rules:
// 1. [Pattern]: Responsive card grid reuses DOMAIN_COLORS and STATUS_COLORS patterns from EventTicketCard.
// 2. [Constraint]: Cards show metadata only -- no markdown content loaded until selected.
/**
 * Responsive report card grid for the Reports page State 1.
 * Displays persisted report metadata in a multi-column grid.
 */
import type { ReportMeta } from '../api/types';
import { DOMAIN_COLORS } from '../constants/colors';

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
  // Filter by search
  const filtered = reports.filter((r) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return r.service.toLowerCase().includes(q)
      || r.event_id.toLowerCase().includes(q)
      || r.reason.toLowerCase().includes(q);
  });

  // Sort
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

      {/* Card Grid */}
      {sorted.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#64748b', fontSize: 14, padding: 40 }}>
          {searchQuery ? 'No reports match your search.' : 'No reports yet. Reports are generated when events close.'}
        </div>
      ) : (
        <div className={`grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`}>
          {sorted.map((report) => {
            const domain = (report.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
            const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
            return (
              <div
                key={report.event_id}
                onClick={() => onSelectReport(report.event_id)}
                style={{
                  padding: '12px 14px', borderRadius: 8, cursor: 'pointer',
                  background: '#1e293b', borderLeft: `4px solid ${domainColor.border}`,
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#334155'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#1e293b'; }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <strong style={{ color: '#e2e8f0', fontSize: 13 }}>{report.service}</strong>
                  <span style={{
                    background: domainColor.bg, color: domainColor.text,
                    padding: '1px 6px', borderRadius: 10, fontSize: 9, fontWeight: 600,
                    textTransform: 'uppercase',
                  }}>{domain}</span>
                </div>
                <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={report.reason}>
                  {report.reason}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b' }}>
                  <span>{report.turns} turns</span>
                  <span>{new Date(report.closed_at).toLocaleDateString()}</span>
                </div>
                <div style={{ fontSize: 10, color: '#475569', marginTop: 4, fontFamily: 'monospace' }}>
                  {report.event_id}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
