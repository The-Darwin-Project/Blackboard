// BlackBoard/ui/src/components/InsightsPage.tsx
// @ai-rules:
// 1. [Pattern]: Reads selectedEventId from OpsStateContext (same as Dashboard ConversationFeed).
// 2. [Pattern]: 3 states: no event selected, no observations, populated grid.
// 3. [Constraint]: Uses snake_case matching API types.
/**
 * FRIDAY Insights page -- observation series for the selected event.
 */
import { Eye, BarChart3, Archive } from 'lucide-react';
import { useOpsState } from '../contexts/OpsStateContext';
import { useObservations } from '../hooks/useObservations';
import { useActiveEvents } from '../hooks/useQueue';
import ObservationCard from './ObservationCard';

export default function InsightsPage() {
  const { selectedEventId } = useOpsState();
  const { data: activeEvents } = useActiveEvents();

  const isActive = activeEvents?.some(e => e.id === selectedEventId) ?? false;
  const isClosed = selectedEventId ? !isActive : false;

  const { data, isLoading, isError } = useObservations(selectedEventId, isActive);

  if (!selectedEventId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-secondary gap-3">
        <Eye size={32} className="text-text-muted" />
        <p>Select an event to view FRIDAY's observations</p>
      </div>
    );
  }

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
        <p>FRIDAY hasn't recorded observations for this event yet</p>
        <p className="text-xs text-text-muted">{selectedEventId}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-medium text-text-primary">
            Observations — {selectedEventId}
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            {observations.length} series • Event age {data?.event_age_minutes ?? 0}m
          </p>
        </div>
        {isClosed && (
          <span className="flex items-center gap-1 text-xs text-text-muted bg-bg-tertiary px-2 py-1 rounded">
            <Archive size={12} />
            Archived
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {observations.map(series => (
          <ObservationCard key={series.name} series={series} />
        ))}
      </div>
    </div>
  );
}
