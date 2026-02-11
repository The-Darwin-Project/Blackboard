// BlackBoard/ui/src/components/WaitingBell.tsx
/**
 * Notification bell for events waiting on user action (approval or feedback).
 * Shows badge count, color-coded urgency, and shakes after 1 hour.
 */
import { useState, useEffect } from 'react';
import { useActiveEvents } from '../hooks/useQueue';
import { getEventDocument } from '../api/client';

interface WaitingEvent {
  id: string;
  service: string;
  waitingSince: number; // Unix timestamp
  waitingFor: string;   // "user"
  lastThoughts: string; // Brain's message to user
  isPendingApproval: boolean;
}

export default function WaitingBell({ onEventClick }: { onEventClick: (eventId: string) => void }) {
  const { data: activeEvents } = useActiveEvents();
  const [waitingEvents, setWaitingEvents] = useState<WaitingEvent[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [now, setNow] = useState(Date.now());

  // Tick every 30s to update relative times and urgency colors
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch full event docs for active events and find ones waiting for user
  useEffect(() => {
    if (!activeEvents?.length) {
      setWaitingEvents([]);
      return;
    }

    const fetchWaiting = async () => {
      const waiting: WaitingEvent[] = [];
      for (const evt of activeEvents) {
        try {
          const doc = await getEventDocument(evt.id);
          if (!doc?.conversation?.length) continue;
          const lastTurn = doc.conversation[doc.conversation.length - 1];
          if (lastTurn.waitingFor === 'user') {
            waiting.push({
              id: doc.id,
              service: doc.service,
              waitingSince: lastTurn.timestamp * 1000, // Convert to ms
              waitingFor: lastTurn.waitingFor,
              lastThoughts: lastTurn.thoughts || 'Waiting for your response',
              isPendingApproval: lastTurn.pendingApproval || false,
            });
          }
        } catch {
          // Event may have been closed between listing and fetching
        }
      }
      setWaitingEvents(waiting);
    };

    fetchWaiting();
  }, [activeEvents]);

  const count = waitingEvents.length;

  // Urgency classification
  const getUrgency = (waitingSince: number) => {
    const minutesAgo = (now - waitingSince) / 60000;
    if (minutesAgo > 60) return 'critical';  // > 1 hour
    if (minutesAgo > 30) return 'warning';   // > 30 min
    return 'normal';                          // < 30 min
  };

  const hasCritical = waitingEvents.some(e => getUrgency(e.waitingSince) === 'critical');
  const hasWarning = waitingEvents.some(e => getUrgency(e.waitingSince) === 'warning');

  // Badge color
  const badgeColor = hasCritical ? '#ef4444' : hasWarning ? '#eab308' : '#3b82f6';

  // Shake animation for critical items (CSS keyframes injected inline)
  const shakeStyle = hasCritical ? {
    animation: 'bellShake 0.5s ease-in-out infinite',
  } : {};

  const formatAgo = (ts: number) => {
    const min = Math.floor((now - ts) / 60000);
    if (min < 1) return 'just now';
    if (min < 60) return `${min}m ago`;
    const hrs = Math.floor(min / 60);
    return `${hrs}h ${min % 60}m ago`;
  };

  return (
    <>
      {/* Inject shake keyframes */}
      <style>{`
        @keyframes bellShake {
          0%, 100% { transform: rotate(0); }
          25% { transform: rotate(8deg); }
          75% { transform: rotate(-8deg); }
        }
      `}</style>

      <div style={{ position: 'relative', display: 'inline-block' }}>
        {/* Bell icon */}
        <button
          onClick={() => count > 0 && setIsOpen(!isOpen)}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '4px 8px',
            fontSize: 20,
            ...shakeStyle,
          }}
          title={count > 0 ? `${count} event${count > 1 ? 's' : ''} waiting for you` : 'No events waiting'}
        >
          🔔
        </button>

        {/* Badge -- only shown when events are waiting */}
        {count > 0 && (
          <span style={{
            position: 'absolute',
            top: 0,
            right: 2,
            background: badgeColor,
            color: '#fff',
            fontSize: 10,
            fontWeight: 700,
            width: 18,
            height: 18,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}>
            {count}
          </span>
        )}

        {/* Dropdown */}
        {isOpen && (
          <div style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            width: 340,
            background: '#1e293b',
            border: '1px solid #334155',
            borderRadius: 8,
            boxShadow: '0 10px 40px rgba(0,0,0,0.5)',
            zIndex: 1000,
            maxHeight: 400,
            overflow: 'auto',
          }}>
            <div style={{
              padding: '10px 14px',
              borderBottom: '1px solid #334155',
              fontSize: 12,
              fontWeight: 600,
              color: '#e2e8f0',
            }}>
              Waiting for you ({count})
            </div>

            {waitingEvents
              .sort((a, b) => a.waitingSince - b.waitingSince) // Oldest first
              .map((evt) => {
                const urgency = getUrgency(evt.waitingSince);
                const dotColor = urgency === 'critical' ? '#ef4444'
                               : urgency === 'warning' ? '#eab308'
                               : '#3b82f6';

                return (
                  <div
                    key={evt.id}
                    onClick={() => { onEventClick(evt.id); setIsOpen(false); }}
                    style={{
                      padding: '10px 14px',
                      borderBottom: '1px solid #334155',
                      cursor: 'pointer',
                      display: 'flex',
                      gap: 10,
                      alignItems: 'flex-start',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#334155')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    {/* Urgency dot */}
                    <span style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: dotColor,
                      flexShrink: 0,
                      marginTop: 4,
                      animation: urgency === 'critical' ? 'bellShake 1s ease-in-out infinite' : 'none',
                    }} />

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0' }}>
                          {evt.service}
                        </span>
                        <span style={{ fontSize: 10, color: '#64748b' }}>
                          {formatAgo(evt.waitingSince)}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                        {evt.isPendingApproval ? '⏳ Approve/Reject plan' : '💬 Feedback requested'}
                      </div>
                      <div style={{
                        fontSize: 11,
                        color: '#64748b',
                        marginTop: 4,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {evt.lastThoughts?.substring(0, 80)}...
                      </div>
                      <div style={{ fontSize: 10, color: '#475569', fontFamily: 'monospace', marginTop: 2 }}>
                        {evt.id}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </>
  );
}
