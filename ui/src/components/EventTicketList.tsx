// BlackBoard/ui/src/components/EventTicketList.tsx
// @ai-rules:
// 1. [Pattern]: Combines active (useActiveEvents) + closed (useQuery) events with time partitioning.
// 2. [Pattern]: Recent closed events (< 30 min) always visible; older closed behind toggle.
// 3. [Constraint]: closeEvent uses REST POST for reliability (same as ConversationFeed).
/**
 * Event ticket list with active/closed toggle.
 * Displayed in the middle panel "Tickets" tab.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useActiveEvents } from '../hooks/useQueue';
import { getClosedEvents, closeEvent } from '../api/client';
import type { ActiveEvent } from '../api/types';
import EventTicketCard from './EventTicketCard';

interface EventTicketListProps {
  onEventSelect: (id: string) => void;
  onEventClose?: () => void;
  selectedEventId: string | null;
}

export default function EventTicketList({ onEventSelect, onEventClose, selectedEventId }: EventTicketListProps) {
  const [showOlderClosed, setShowOlderClosed] = useState(false);

  const { data: activeEvents, isLoading } = useActiveEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(20),
    refetchOnWindowFocus: true,
    refetchInterval: 10_000,
  });

  // Time-based partitioning: recent closed (< 30 min) always visible
  const recentClosed = (closedEvents || []).filter((evt) => {
    if (!evt.created) return false;
    const age = Date.now() - new Date(evt.created).getTime();
    return age < 30 * 60 * 1000;
  });
  const olderClosed = (closedEvents || []).filter((evt) => {
    if (!evt.created) return true;
    const age = Date.now() - new Date(evt.created).getTime();
    return age >= 30 * 60 * 1000;
  });

  const allEvents: ActiveEvent[] = [
    ...(activeEvents || []),
    ...recentClosed,
    ...(showOlderClosed ? olderClosed : []),
  ];

  const handleClose = (id: string) => {
    closeEvent(id);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header with toggle */}
      <div style={{
        padding: '8px 12px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', borderBottom: '1px solid #334155', flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>
          {activeEvents?.length || 0} active
        </span>
        <button
          onClick={() => setShowOlderClosed(!showOlderClosed)}
          style={{
            background: 'none', border: '1px solid #334155', borderRadius: 4,
            color: '#94a3b8', fontSize: 10, padding: '2px 8px', cursor: 'pointer',
          }}
        >
          {showOlderClosed
            ? `Hide Closed (${olderClosed.length})`
            : `Show Closed (${olderClosed.length})`}
        </button>
      </div>

      {/* Scrollable ticket grid */}
      <div style={{
        flex: 1, overflow: 'auto', padding: '12px 16px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: 12,
        alignContent: 'start',
      }}>
        {allEvents.map((evt) => (
          <EventTicketCard
            key={evt.id}
            event={evt}
            isSelected={selectedEventId === evt.id}
            onSelect={() => selectedEventId === evt.id && onEventClose ? onEventClose() : onEventSelect(evt.id)}
            onClose={handleClose}
          />
        ))}
        {isLoading && allEvents.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13, padding: '24px 0', textAlign: 'center', gridColumn: '1 / -1' }}>
            Loading events...
          </p>
        )}
        {!isLoading && allEvents.length === 0 && (
          <p style={{ color: '#64748b', fontSize: 13, padding: '12px 0', textAlign: 'center', gridColumn: '1 / -1' }}>
            No events
          </p>
        )}
      </div>
    </div>
  );
}
