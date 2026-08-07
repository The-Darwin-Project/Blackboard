// BlackBoard/ui/src/components/InsightsPage.tsx
// @ai-rules:
// 1. [Pattern]: Reads selectedEventId from OpsStateContext (same as Dashboard ConversationFeed).
// 2. [Pattern]: Default view = global (all events, 7-day). Event selection = drill-down.
// 3. [Constraint]: Uses snake_case matching API types.
// 4. [Pattern]: Toolbar with Generate Report / Bulk Delete / Export. Selection via Set<string>.
/**
 * FRIDAY Insights page -- global observation timeline with per-event drill-down.
 */
import { useCallback, useMemo, useState } from 'react';
import { Globe, BarChart3, Archive, Filter, FileText, Trash2, Download, Loader2 } from 'lucide-react';
import { useOpsControl } from '../contexts/OpsStateContext';
import { useObservations, useGlobalObservations } from '../hooks/useObservations';
import { useActiveEvents } from '../hooks/useQueue';
import { useDeleteObservation, useRenameObservation, useBulkDeleteObservations } from '../hooks/useObservationsMutations';
import { generateObservationsReport, exportObservations } from '../api/client';
import ObservationCard from './ObservationCard';

const MAX_REPORT_SERIES = 10;

export default function InsightsPage() {
  const { selectedEventId } = useOpsControl();
  const { data: activeEvents } = useActiveEvents();
  const [serviceFilter, setServiceFilter] = useState<string>('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);

  const deleteMutation = useDeleteObservation();
  const renameMutation = useRenameObservation();
  const bulkDeleteMutation = useBulkDeleteObservations();

  const isActive = activeEvents?.some(e => e.id === selectedEventId) ?? false;
  const isClosed = selectedEventId ? !isActive : false;

  const globalQuery = useGlobalObservations(
    serviceFilter ? { service: serviceFilter } : undefined,
  );
  const eventQuery = useObservations(selectedEventId, isActive);

  const isEventMode = !!selectedEventId;
  const { data, isLoading, isError } = isEventMode ? eventQuery : globalQuery;

  const services = useMemo(() => {
    if (!globalQuery.data?.observations) return [];
    const svcSet = new Set<string>();
    for (const s of globalQuery.data.observations) {
      for (const p of s.points) {
        if (p.service) svcSet.add(p.service);
      }
    }
    return [...svcSet].sort();
  }, [globalQuery.data]);

  const toggleSelect = useCallback((name: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const handleDelete = useCallback((name: string) => {
    deleteMutation.mutate(name, {
      onSuccess: () => setSelected(prev => { const n = new Set(prev); n.delete(name); return n; }),
    });
  }, [deleteMutation]);

  const handleRename = useCallback((oldName: string, newName: string) => {
    renameMutation.mutate({ name: oldName, newName }, {
      onSuccess: () => {
        setSelected(prev => {
          if (!prev.has(oldName)) return prev;
          const n = new Set(prev);
          n.delete(oldName);
          n.add(newName);
          return n;
        });
        setServiceFilter('');
      },
    });
  }, [renameMutation]);

  const handleBulkDelete = useCallback(() => {
    const names = [...selected];
    if (!names.length) return;
    if (!confirm(`Delete ${names.length} observation series? This cannot be undone.`)) return;
    bulkDeleteMutation.mutate(names, {
      onSuccess: () => setSelected(new Set()),
    });
  }, [selected, bulkDeleteMutation]);

  const handleGenerateReport = useCallback(async () => {
    setGenerating(true);
    try {
      const { markdown, filename } = await generateObservationsReport([...selected]);
      const blob = new Blob([markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setGenerating(false);
    }
  }, [selected]);

  const handleExport = useCallback(async (format: 'csv' | 'json') => {
    const names = selected.size > 0 ? [...selected] : undefined;
    const result = await exportObservations(format, names);
    const content = typeof result.content === 'string' ? result.content : JSON.stringify(result.content, null, 2);
    const blob = new Blob([content], { type: format === 'csv' ? 'text/csv' : 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    a.click();
    URL.revokeObjectURL(url);
  }, [selected]);

  const handleExportSingle = useCallback(async (name: string) => {
    const result = await exportObservations('csv', [name]);
    const content = typeof result.content === 'string' ? result.content : JSON.stringify(result.content, null, 2);
    const blob = new Blob([content], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary">
        Loading observations...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-muted gap-2">
        <BarChart3 className="w-12 h-12" />
        <p className="text-sm">Unable to load observations</p>
        <p className="text-xs">Check API connection</p>
      </div>
    );
  }

  const observations = data?.observations ?? [];

  if (observations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-secondary gap-3">
        <BarChart3 size={32} className="text-text-muted" />
        <p>
          {isEventMode
            ? "FRIDAY hasn't recorded observations for this event yet"
            : 'No observations recorded in the last 7 days'}
        </p>
        {isEventMode && (
          <p className="text-xs text-text-muted">{selectedEventId}</p>
        )}
      </div>
    );
  }

  const selectionDisabled = selected.size >= MAX_REPORT_SERIES;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-medium text-text-primary flex items-center gap-1.5">
            {isEventMode ? (
              <>Observations — {selectedEventId}</>
            ) : (
              <><Globe size={14} /> Global Observations (7 days)</>
            )}
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            {observations.length} series
            {isEventMode && ` • Event age ${data?.event_age_minutes ?? 0}m`}
            {selected.size > 0 && ` • ${selected.size} selected`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isEventMode && (
            <>
              <button
                onClick={handleGenerateReport}
                disabled={selected.size === 0 || generating}
                title={selected.size > MAX_REPORT_SERIES ? `Maximum ${MAX_REPORT_SERIES} series` : selected.size === 0 ? 'Select series first' : 'Generate analysis report'}
                className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {generating ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
                Report{selected.size > 0 && ` (${selected.size})`}
              </button>

              {selected.size > 0 && (
                <button
                  onClick={handleBulkDelete}
                  disabled={bulkDeleteMutation.isPending}
                  className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded bg-red-600/20 hover:bg-red-600/40 text-red-400 transition-colors"
                >
                  <Trash2 size={12} />
                  Delete ({selected.size})
                </button>
              )}

              <div className="relative group/export">
                <button className="flex items-center gap-1 text-xs px-2 py-1.5 rounded hover:bg-bg-tertiary text-text-secondary">
                  <Download size={12} />
                  Export
                </button>
                <div className="absolute right-0 top-full mt-1 hidden group-hover/export:block bg-bg-tertiary border border-border rounded-md shadow-lg py-1 z-20 min-w-[100px]">
                  <button onClick={() => handleExport('csv')} className="block w-full text-left px-3 py-1.5 text-xs text-text-primary hover:bg-bg-secondary">CSV</button>
                  <button onClick={() => handleExport('json')} className="block w-full text-left px-3 py-1.5 text-xs text-text-primary hover:bg-bg-secondary">JSON</button>
                </div>
              </div>
            </>
          )}

          {!isEventMode && services.length > 1 && (
            <div className="flex items-center gap-1">
              <Filter size={12} className="text-text-muted" />
              <select
                value={serviceFilter}
                onChange={e => setServiceFilter(e.target.value)}
                className="text-xs bg-bg-secondary border border-border-primary rounded px-1.5 py-0.5 text-text-primary"
              >
                <option value="">All services</option>
                {services.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          )}
          {isClosed && (
            <span className="flex items-center gap-1 text-xs text-text-muted bg-bg-tertiary px-2 py-1 rounded">
              <Archive size={12} />
              Archived
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {observations.map(series => (
          <ObservationCard
            key={series.name}
            series={series}
            namePattern={data?.name_pattern}
            selected={selected.has(series.name)}
            selectionDisabled={selectionDisabled}
            onToggleSelect={!isEventMode ? toggleSelect : undefined}
            onDelete={!isEventMode ? handleDelete : undefined}
            onRename={!isEventMode ? handleRename : undefined}
            onExport={!isEventMode ? handleExportSingle : undefined}
          />
        ))}
      </div>
    </div>
  );
}
