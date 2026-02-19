// BlackBoard/ui/src/components/ActivityStream.tsx
// @ai-rules:
// 1. [Pattern]: Uses useEvents() hook which returns ALL ArchitectureEvent types, not just Aligner.
// 2. [Constraint]: Tab label can say "Activity" or "Live Feed" -- component name matches data semantics.
/**
 * Real-time architecture event stream.
 * Extracted from ConversationFeed's "no event selected" fallback view.
 * Displays timestamped entries from the useEvents hook (all event types).
 */
import { useEvents } from '../hooks/useEvents';

export default function ActivityStream() {
  const { data: archEvents, isLoading } = useEvents();

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
      {isLoading && !archEvents ? (
        <p style={{ color: '#94a3b8', fontSize: 13, padding: '24px 0', textAlign: 'center' }}>
          Loading activity...
        </p>
      ) : archEvents && archEvents.length > 0 ? (
        archEvents.slice(0, 30).map((evt, i) => (
          <div
            key={i}
            style={{
              padding: '4px 0',
              fontSize: 13,
              color: '#cbd5e1',
              borderBottom: '1px solid #1e293b',
            }}
          >
            <span style={{ color: '#94a3b8' }}>
              {new Date(evt.timestamp * 1000).toLocaleTimeString()}
            </span>
            {' '}{evt.narrative || evt.type}
            <span style={{ color: '#64748b', fontSize: 11, marginLeft: 6 }}>(AI-generated)</span>
          </div>
        ))
      ) : (
        <p style={{ color: '#94a3b8', fontSize: 13, padding: '12px 0', textAlign: 'center' }}>
          No activity yet. Events will appear when services are monitored.
        </p>
      )}
    </div>
  );
}
