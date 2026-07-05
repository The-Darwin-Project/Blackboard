// BlackBoard/ui/src/components/InsightsPage.tsx
// @ai-rules:
// 1. [Pattern]: Reads selectedEventId from OpsStateContext (same as Dashboard ConversationFeed).
// 2. [Pattern]: Default view = global (all events, 7-day). Event selection = drill-down.
// 3. [Constraint]: Uses snake_case matching API types.
/**
 * FRIDAY Insights page -- global observation timeline with per-event drill-down.
 */
import { useMemo, useState } from 'react';
import { Globe, BarChart3, Archive, Filter } from 'lucide-react';
import { useOpsControl } from '../contexts/OpsStateContext';
import { useObservations } from '../hooks/useObservations';
import { useGlobalObservations } from '../hooks/useObservations';
import { useActiveEvents } from '../hooks/useQueue';
import ObservationCard from './ObservationCard';

export default function InsightsPage() {
  const { selectedEventId } = useOpsControl();
  const { data: activeEvents } = useActiveEvents();
  const [serviceFilter, setServiceFilter] = useState<string>('');

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
          </p>
        </div>
        <div className="flex items-center gap-2">
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
          <ObservationCard key={series.name} series={series} />
        ))}
      </div>
    </div>
  );
}
