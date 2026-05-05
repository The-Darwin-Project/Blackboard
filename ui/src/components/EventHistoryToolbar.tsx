// BlackBoard/ui/src/components/EventHistoryToolbar.tsx
// @ai-rules:
// 1. [Pattern]: Time range presets compute start_time as epoch float. "Custom" is a placeholder for future date picker.
// 2. [Pattern]: Facet filters are dropdown selects. Active non-default filters show as removable pills below.
// 3. [Constraint]: Search input is debounced by the caller, not here. This component fires onChange immediately.
import { useCallback } from 'react';

type ViewMode = 'table' | 'grid';
type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';

interface ToolbarProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  service: string;
  onServiceChange: (s: string) => void;
  source: string;
  onSourceChange: (s: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  serviceOptions: string[];
  sourceOptions: string[];
}

const TIME_RANGES: { key: TimeRange; label: string }[] = [
  { key: '1h', label: '1h' },
  { key: '6h', label: '6h' },
  { key: '24h', label: '24h' },
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
];

export default function EventHistoryToolbar({
  viewMode, onViewModeChange, timeRange, onTimeRangeChange,
  service, onServiceChange, source, onSourceChange,
  searchQuery, onSearchChange, serviceOptions, sourceOptions,
}: ToolbarProps) {
  const clearFilters = useCallback(() => {
    onServiceChange('');
    onSourceChange('');
    onSearchChange('');
    onTimeRangeChange('24h');
  }, [onServiceChange, onSourceChange, onSearchChange, onTimeRangeChange]);

  const hasActiveFilters = service || source || searchQuery || timeRange !== '24h';

  return (
    <div className="flex flex-col gap-2 p-3 border-b border-border-primary bg-bg-secondary">
      {/* Row 1: View toggle + Time range + Search */}
      <div className="flex items-center gap-3">
        {/* View toggle */}
        <div className="flex rounded-md border border-border-primary overflow-hidden">
          <button
            onClick={() => onViewModeChange('grid')}
            aria-pressed={viewMode === 'grid'}
            className={`px-2 py-1.5 text-xs ${viewMode === 'grid' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:bg-bg-tertiary'}`}
            title="Grid view"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1 1h6v6H1zm8 0h6v6H9zM1 9h6v6H1zm8 0h6v6H9z"/></svg>
          </button>
          <button
            onClick={() => onViewModeChange('table')}
            aria-pressed={viewMode === 'table'}
            className={`px-2 py-1.5 text-xs ${viewMode === 'table' ? 'bg-accent/20 text-accent' : 'text-text-muted hover:bg-bg-tertiary'}`}
            title="Table view"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1 1h14v3H1zm0 5h14v3H1zm0 5h14v3H1z"/></svg>
          </button>
        </div>

        {/* Time range */}
        <div className="flex rounded-md border border-border-primary overflow-hidden">
          {TIME_RANGES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => onTimeRangeChange(key)}
              className={`px-2.5 py-1 text-xs font-medium ${timeRange === key ? 'bg-accent/20 text-accent' : 'text-text-muted hover:bg-bg-tertiary'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Search */}
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search event ID, service, reason..."
          aria-label="Search events"
          className="flex-1 bg-bg-primary border border-border-primary rounded-md px-3 py-1.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
        />
      </div>

      {/* Row 2: Facet filters + clear */}
      <div className="flex items-center gap-2">
        <select
          value={service}
          onChange={(e) => onServiceChange(e.target.value)}
          className="bg-bg-primary border border-border-primary rounded-md px-2 py-1 text-xs text-text-secondary"
        >
          <option value="">All services</option>
          {serviceOptions.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <select
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          className="bg-bg-primary border border-border-primary rounded-md px-2 py-1 text-xs text-text-secondary"
        >
          <option value="">All sources</option>
          {sourceOptions.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-text-muted hover:text-accent ml-auto"
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}

export function timeRangeToEpoch(range: TimeRange): { startTime: number; endTime: number } {
  const now = Date.now() / 1000;
  const durations: Record<TimeRange, number> = {
    '1h': 3600,
    '6h': 21600,
    '24h': 86400,
    '7d': 604800,
    '30d': 2592000,
  };
  return { startTime: now - durations[range], endTime: now };
}
