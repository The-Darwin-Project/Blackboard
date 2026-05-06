// BlackBoard/ui/src/components/EventHistory.tsx
// @ai-rules:
// 1. [Pattern]: Master-detail layout. Table/grid on left, ReportContent on right (50% split).
// 2. [Pattern]: Feature-flag gated via VITE_EVENT_HISTORY_ENABLED in App.tsx, not here.
// 3. [Pattern]: URL state via useSearchParams for shareable filter links.
// 4. [Constraint]: Below 1024px, side panel renders full-width below the list.
import { useState, useMemo, useCallback, useEffect } from 'react';
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

      <div className="flex-1 flex overflow-hidden max-lg:flex-col">
        {/* List (table or grid) */}
        <div className={`flex flex-col overflow-hidden ${selectedId ? 'w-1/2 max-lg:w-full max-lg:h-1/2' : 'w-full'}`}>
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
        </div>

        {/* Side panel */}
        {selectedId && (
          <div className="w-1/2 max-lg:w-full max-lg:h-1/2 border-l max-lg:border-l-0 max-lg:border-t border-border-primary flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-border-primary flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => {
                  setSelectedId(null);
                  window.dispatchEvent(new CustomEvent('darwin:expandSidebar'));
                }}
                className="text-xs bg-accent text-white rounded-md px-3 py-1 font-medium hover:bg-accent/80"
              >
                &#x2190; Close
              </button>
              {selectedReport && (
                <span className="text-xs text-text-muted">
                  {selectedReport.service} &middot; {selectedReport.event_id}
                </span>
              )}
            </div>
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
        )}
      </div>
    </div>
  );
}
