// BlackBoard/ui/src/components/EventHistory.tsx
// @ai-rules:
// 1. [Pattern]: Two-state layout. No selection: full table/grid. Selection: compact card strip + full-width report.
// 2. [Pattern]: Feature-flag gated via VITE_EVENT_HISTORY_ENABLED in App.tsx, not here.
// 3. [Pattern]: URL state via useSearchParams for shareable filter links.
// 4. [Pattern]: CompactCardStrip auto-scrolls selected card into view. Horizontal scroll for navigation.
import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getReport } from '../api/client';
import { useReportSearch } from '../hooks/useReportSearch';
import EventHistoryToolbar, { timeRangeToEpoch } from './EventHistoryToolbar';
import EventHistoryTable from './EventHistoryTable';
import EventHistoryGrid from './EventHistoryGrid';
import ReportContent from './ReportContent';
import ReportToolbar from './ReportToolbar';

type ViewMode = 'table' | 'grid';
type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

export default function EventHistory() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [viewMode, setViewMode] = useState<ViewMode>(
    () => (localStorage.getItem('darwin:eventHistoryView') as ViewMode) || 'table',
  );
  const [timeRange, setTimeRange] = useState<TimeRange>(
    () => (searchParams.get('range') as TimeRange) || '24h',
  );
  const [service, setService] = useState(() => searchParams.get('service') || '');
  const [source, setSource] = useState(() => searchParams.get('source') || '');
  const [searchQuery, setSearchQuery] = useState(() => searchParams.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => searchParams.get('id'),
  );

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    localStorage.setItem('darwin:eventHistoryView', viewMode);
  }, [viewMode]);

  const filters = useMemo(() => {
    const { startTime, endTime } = timeRangeToEpoch(timeRange);
    return {
      startTime,
      endTime,
      service: service || undefined,
      source: source || undefined,
      q: debouncedQuery || undefined,
    };
  }, [timeRange, service, source, debouncedQuery]);

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useReportSearch(filters);

  const allReports = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  const serviceOptions = useMemo(() => {
    const set = new Set(allReports.map((r) => r.service));
    return [...set].sort();
  }, [allReports]);

  const sourceOptions = useMemo(() => {
    const set = new Set(allReports.map((r) => r.source));
    for (const s of ['aligner', 'chat', 'headhunter', 'jarvis', 'slack', 'timekeeper']) set.add(s);
    return [...set].sort();
  }, [allReports]);

  const syncParams = useCallback(() => {
    const p: Record<string, string> = {};
    if (timeRange !== '24h') p.range = timeRange;
    if (service) p.service = service;
    if (source) p.source = source;
    if (searchQuery) p.q = searchQuery;
    if (selectedId) p.id = selectedId;
    setSearchParams(p, { replace: true });
  }, [timeRange, service, source, searchQuery, selectedId, setSearchParams]);

  useEffect(syncParams, [syncParams]);

  const onSelect = useCallback((id: string) => {
    if (!selectedId) {
      window.dispatchEvent(new CustomEvent('darwin:collapseSidebar'));
    }
    setSelectedId(id);
  }, [selectedId]);

  const { data: selectedReport } = useQuery({
    queryKey: ['report', selectedId],
    queryFn: () => getReport(selectedId!),
    enabled: !!selectedId,
  });

  return (
    <div className="h-full flex flex-col">
      <EventHistoryToolbar
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        service={service}
        onServiceChange={setService}
        source={source}
        onSourceChange={setSource}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        serviceOptions={serviceOptions}
        sourceOptions={sourceOptions}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedId ? (
          <>
            {/* Collapsed: horizontal card strip */}
            <CompactCardStrip
              reports={allReports}
              selectedId={selectedId}
              onSelect={onSelect}
              onClose={() => {
                setSelectedId(null);
                window.dispatchEvent(new CustomEvent('darwin:expandSidebar'));
              }}
            />

            {/* Report detail -- full width, full remaining height */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {selectedReport ? (
                <>
                  <ReportContent report={selectedReport} />
                  <ReportToolbar markdown={selectedReport.markdown} eventId={selectedReport.event_id} />
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-text-muted">
                  Loading report...
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            {/* Expanded: full table or grid */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {isLoading ? (
                <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
                  Loading events...
                </div>
              ) : isError ? (
                <div className="flex-1 flex items-center justify-center text-red-400 text-sm">
                  Failed to load events.
                </div>
              ) : viewMode === 'table' ? (
                <EventHistoryTable reports={allReports} selectedId={selectedId} onSelect={onSelect} />
              ) : (
                <EventHistoryGrid reports={allReports} selectedId={selectedId} onSelect={onSelect} />
              )}
            </div>

            {/* Load more */}
            {hasNextPage && (
              <div className="p-3 border-t border-border-primary text-center">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="text-xs text-accent hover:underline disabled:opacity-50"
                >
                  {isFetchingNextPage ? 'Loading...' : `Load more (showing ${allReports.length} results)`}
                </button>
              </div>
            )}
            {!hasNextPage && allReports.length > 0 && (
              <div className="p-2 text-center text-xs text-text-muted">
                All {allReports.length} results
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

import { DOMAIN_COLORS, SEVERITY_COLORS } from '../constants/colors';
import { resolveDescription } from '../utils/eventFormat';

function CompactCardStrip({ reports, selectedId, onSelect, onClose }: {
  reports: import('../api/types').ReportMeta[];
  selectedId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }, [selectedId]);

  return (
    <div className="flex-shrink-0 border-b border-border-primary bg-bg-secondary">
      <div className="flex items-center gap-2 px-2 py-1.5">
        <button
          onClick={onClose}
          className="flex-shrink-0 text-xs bg-accent text-white rounded-md px-2.5 py-1 font-medium hover:bg-accent/80"
          title="Back to full list"
        >
          &#x2190;
        </button>
        <div ref={scrollRef} className="flex-1 flex gap-1.5 overflow-x-auto scrollbar-thin py-0.5">
          {reports.map((r) => {
            const isSelected = r.event_id === selectedId;
            const domain = (r.domain || 'complicated') as keyof typeof DOMAIN_COLORS;
            const dc = DOMAIN_COLORS[domain] || DOMAIN_COLORS.complicated;
            const sc = SEVERITY_COLORS[r.severity] || SEVERITY_COLORS.info;
            return (
              <button
                key={r.event_id}
                ref={isSelected ? selectedRef : undefined}
                onClick={() => onSelect(r.event_id)}
                className={`flex-shrink-0 rounded-lg px-3 py-1.5 text-left transition-all outline-none ${
                  isSelected ? 'ring-2 ring-accent bg-bg-tertiary' : 'bg-bg-primary hover:bg-bg-tertiary'
                }`}
                style={{ borderLeft: `3px solid ${dc.border}`, minWidth: 180, maxWidth: 240 }}
              >
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-xs font-medium text-text-primary truncate">{r.service}</span>
                  <span style={{ background: sc.bg, color: sc.text, padding: '1px 6px', borderRadius: 8, fontSize: 10, fontWeight: 600 }}>
                    {sc.label}
                  </span>
                </div>
                <div className="text-[11px] text-text-muted truncate">
                  {resolveDescription(r.display_text, r.reason)}
                </div>
                <div className="text-[10px] text-text-muted mt-0.5">
                  {new Date(r.closed_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })} · {r.turns}t
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
