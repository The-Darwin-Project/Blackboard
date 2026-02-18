// BlackBoard/ui/src/components/ReportsPage.tsx
// @ai-rules:
// 1. [Pattern]: 3-state layout: Grid -> Report+Notch -> Report+Sidebar.
// 2. [Pattern]: useSearchParams for ?id= deep-link. Clear param on "Back to Grid".
// 3. [Constraint]: No sessionStorage persistence. Refresh without ?id= returns to Grid.
/**
 * Report Viewer page with 3-state collapse layout.
 * State 1: Responsive card grid (default)
 * State 2: Full-width report + collapsed notch on left
 * State 3: 1/3 sidebar card list + 2/3 report viewer
 */
import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getReports, getReport } from '../api/client';
import type { ReportMeta } from '../api/types';
import ReportGrid from './ReportGrid';
import ReportContent from './ReportContent';
import ReportToolbar from './ReportToolbar';
import { DOMAIN_COLORS } from '../constants/colors';

export default function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedReportId, setSelectedReportId] = useState<string | null>(
    () => searchParams.get('id'),
  );
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'date' | 'service' | 'domain' | 'severity'>('date');

  // Fetch report list
  const { data: reports = [] } = useQuery({
    queryKey: ['reports'],
    queryFn: () => getReports(200),
    refetchOnWindowFocus: true,
  });

  // Fetch selected report content
  const { data: selectedReport } = useQuery({
    queryKey: ['report', selectedReportId],
    queryFn: () => getReport(selectedReportId!),
    enabled: !!selectedReportId,
  });

  const onSelectReport = (eventId: string) => {
    setSelectedReportId(eventId);
    setSidebarExpanded(false);
    setSearchParams({ id: eventId });
  };

  const onBackToGrid = () => {
    setSelectedReportId(null);
    setSidebarExpanded(false);
    setSearchParams({});
  };

  // Sidebar cards (filtered + sorted) -- must be above any early return to satisfy Rules of Hooks
  const sidebarReports = useMemo(() => {
    let filtered = reports;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = reports.filter((r) =>
        r.service.toLowerCase().includes(q)
        || r.event_id.toLowerCase().includes(q)
        || r.reason.toLowerCase().includes(q),
      );
    }
    return [...filtered].sort((a, b) => {
      if (sortBy === 'service') return a.service.localeCompare(b.service);
      if (sortBy === 'domain') return a.domain.localeCompare(b.domain);
      if (sortBy === 'severity') {
        const order = { critical: 0, warning: 1, info: 2 };
        return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
      }
      return new Date(b.closed_at).getTime() - new Date(a.closed_at).getTime();
    });
  }, [reports, searchQuery, sortBy]);

  // ========== State 1: Grid ==========
  if (!selectedReportId) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <ReportGrid
          reports={reports}
          onSelectReport={onSelectReport}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          sortBy={sortBy}
          onSortChange={setSortBy}
        />
      </div>
    );
  }

  // ========== State 2 & 3: Report View ==========
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Report view */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Left: Notch or Sidebar */}
        {sidebarExpanded ? (
          /* State 3: 1/3 Sidebar */
          <div style={{
            width: '33%', minWidth: 280, maxWidth: 400,
            borderRight: '1px solid #334155', display: 'flex', flexDirection: 'column',
            background: '#0f172a', flexShrink: 0,
          }}>
            <div style={{
              padding: '8px 12px', borderBottom: '1px solid #334155',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                style={{
                  flex: 1, background: '#1e293b', border: '1px solid #334155',
                  borderRadius: 6, padding: '4px 8px', color: '#e2e8f0', fontSize: 12,
                }}
              />
              <button
                onClick={() => setSidebarExpanded(false)}
                style={{
                  marginLeft: 8, background: 'transparent', border: 'none',
                  color: '#64748b', fontSize: 16, cursor: 'pointer',
                }}
                title="Collapse sidebar"
              >&#x276E;</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
              {sidebarReports.map((r) => (
                <SidebarCard
                  key={r.event_id}
                  report={r}
                  isSelected={r.event_id === selectedReportId}
                  onClick={() => onSelectReport(r.event_id)}
                />
              ))}
            </div>
          </div>
        ) : (
          /* State 2: Notch */
          <div
            data-no-print
            onClick={() => setSidebarExpanded(true)}
            style={{
              width: 16, flexShrink: 0, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: '#1e293b', borderRight: '1px solid #334155',
            }}
            title="Show report list"
          >
            <span style={{ color: '#64748b', fontSize: 14 }}>&#x276F;</span>
          </div>
        )}

        {/* Right: Report Content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* Back button header */}
          <div data-no-print style={{
            padding: '6px 12px', borderBottom: '1px solid #334155',
            display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
          }}>
            <button
              onClick={onBackToGrid}
              style={{
                background: '#3b82f6', border: 'none', borderRadius: 6,
                color: '#ffffff', padding: '6px 14px', cursor: 'pointer', fontSize: 13,
                fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              <span style={{ fontSize: 16, lineHeight: 1 }}>&#x2190;</span>
              Back to Grid
            </button>
            {selectedReport && (
              <span style={{ fontSize: 12, color: '#64748b' }}>
                {selectedReport.service} &middot; {selectedReport.event_id}
              </span>
            )}
          </div>

          {/* Markdown content */}
          {selectedReport ? (
            <ReportContent markdown={selectedReport.markdown} />
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
              Loading report...
            </div>
          )}

          {/* Toolbar */}
          {selectedReport && (
            <ReportToolbar markdown={selectedReport.markdown} eventId={selectedReport.event_id} />
          )}
        </div>
      </div>
    </div>
  );
}

/** Compact card for sidebar (State 3). */
function SidebarCard({ report, isSelected, onClick }: {
  report: ReportMeta; isSelected: boolean; onClick: () => void;
}) {
  const domain = (report.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
  const domainColor = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
  return (
    <div
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      role="button"
      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = '#334155'; }}
      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = '#1e293b'; }}
      style={{
        padding: '8px 10px', marginBottom: 4, borderRadius: 6, cursor: 'pointer',
        background: isSelected ? '#334155' : '#1e293b',
        borderLeft: `3px solid ${domainColor.border}`,
        transition: 'background 0.15s',
        outline: 'none',
      }}
    >
      <div style={{ fontSize: 12, color: '#e2e8f0', fontWeight: isSelected ? 600 : 400 }}>
        {report.service}
      </div>
      <div style={{ fontSize: 11, color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {report.reason}
      </div>
      <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>
        {new Date(report.closed_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })} &middot; {report.turns} turns
      </div>
    </div>
  );
}
