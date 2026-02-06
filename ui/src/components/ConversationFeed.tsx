// BlackBoard/ui/src/components/ConversationFeed.tsx
/**
 * Unified group-chat view with real-time WebSocket updates.
 * Layout: Events panel (top) + Conversation stream (bottom) + Chat input
 */
import { useState, useEffect, useRef } from 'react';
import { useActiveEvents, useEventDocument, useQueueInvalidation } from '../hooks/useQueue';
import { useEvents } from '../hooks/useEvents';
import { useChat } from '../hooks/useChat';
import { useWebSocket } from '../hooks/useWebSocket';
import { approveEvent, getClosedEvents } from '../api/client';
import type { ConversationTurn } from '../api/types';
import { useQuery } from '@tanstack/react-query';

const ACTOR_COLORS: Record<string, string> = {
  brain: '#8b5cf6',
  architect: '#3b82f6',
  sysadmin: '#f59e0b',
  developer: '#10b981',
  aligner: '#6b7280',
  user: '#ec4899',
};

const STATUS_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  new: { bg: '#1e40af', text: '#93c5fd', label: 'New' },
  active: { bg: '#065f46', text: '#6ee7b7', label: 'Active' },
  waiting_approval: { bg: '#92400e', text: '#fcd34d', label: 'Awaiting' },
  deferred: { bg: '#4c1d95', text: '#c4b5fd', label: 'Deferred' },
  resolved: { bg: '#14532d', text: '#86efac', label: 'Resolved' },
  closed: { bg: '#374151', text: '#9ca3af', label: 'Closed' },
};

// ============================================================================
// Sub-components
// ============================================================================

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_COLORS[status] || STATUS_COLORS.closed;
  return (
    <span style={{
      background: s.bg, color: s.text, padding: '1px 8px',
      borderRadius: 10, fontSize: 10, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {s.label}
    </span>
  );
}

function EventCard({
  evt,
  selected,
  onClick,
}: {
  evt: Record<string, unknown>;
  selected: boolean;
  onClick: () => void;
}) {
  const status = evt.status as string || 'active';
  const statusStyle = STATUS_COLORS[status] || STATUS_COLORS.active;
  return (
    <div
      onClick={onClick}
      style={{
        padding: '8px 10px', marginBottom: 4, borderRadius: 8,
        background: selected ? '#334155' : '#1e293b',
        borderLeft: `3px solid ${statusStyle.text}`,
        cursor: 'pointer', fontSize: 13, transition: 'background 0.15s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
        <strong style={{ color: '#e2e8f0' }}>{evt.service as string}</strong>
        <StatusBadge status={status} />
      </div>
      <div style={{ color: '#94a3b8', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {(evt.reason as string)?.slice(0, 60)}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11, color: '#64748b' }}>
        <span>{evt.source as string}</span>
        <span>{evt.turns as number} turns</span>
      </div>
    </div>
  );
}

function AttachmentCard({ filename, content }: { filename: string; content: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      border: '1px solid #334155', borderRadius: 8, marginTop: 8,
      background: '#0f172a', overflow: 'hidden',
    }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          padding: '6px 12px', cursor: 'pointer', display: 'flex',
          justifyContent: 'space-between', alignItems: 'center',
          background: '#1e293b', fontSize: 12, color: '#94a3b8',
        }}
      >
        <span>{filename}</span>
        <span>{expanded ? '[-]' : '[+]'}</span>
      </div>
      {expanded && (
        <pre style={{
          padding: 12, fontSize: 12, color: '#e2e8f0',
          overflow: 'auto', maxHeight: 400, margin: 0,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {content}
        </pre>
      )}
    </div>
  );
}

function TurnBubble({ turn, eventId }: { turn: ConversationTurn; eventId?: string }) {
  const color = ACTOR_COLORS[turn.actor] || '#6b7280';
  return (
    <div style={{ borderLeft: `3px solid ${color}`, paddingLeft: 12, marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
        <span style={{
          background: color, color: '#fff', padding: '2px 8px',
          borderRadius: 12, fontSize: 12, fontWeight: 600,
        }}>
          {turn.actor}
        </span>
        <span style={{ fontSize: 12, color: '#888' }}>{turn.action}</span>
        <span style={{ fontSize: 11, color: '#666' }}>
          {new Date(turn.timestamp * 1000).toLocaleTimeString()}
        </span>
      </div>
      {turn.thoughts && <p style={{ margin: '4px 0', fontSize: 14, color: '#e2e8f0' }}>{turn.thoughts}</p>}
      {turn.result && <p style={{ margin: '4px 0', fontSize: 14, color: '#4ade80' }}>{turn.result}</p>}
      {turn.plan && (
        <pre style={{
          background: '#1e1e2e', padding: 12, borderRadius: 8,
          fontSize: 13, overflow: 'auto', maxHeight: 300, color: '#e2e8f0',
        }}>
          {turn.plan}
        </pre>
      )}
      {turn.evidence && (
        <p style={{ margin: '4px 0', fontSize: 13, color: '#94a3b8' }}>Evidence: {turn.evidence}</p>
      )}
      {turn.pendingApproval && eventId && (
        <button
          onClick={() => approveEvent(eventId)}
          style={{
            background: '#22c55e', color: '#fff', border: 'none',
            padding: '6px 16px', borderRadius: 6, cursor: 'pointer',
            marginTop: 8, fontWeight: 600,
          }}
        >
          Approve Plan
        </button>
      )}
    </div>
  );
}

function ProgressDots({ agent }: { agent: string }) {
  const color = ACTOR_COLORS[agent] || '#6b7280';
  return (
    <div style={{ borderLeft: `3px solid ${color}`, paddingLeft: 12, marginBottom: 8, opacity: 0.7 }}>
      <span style={{
        background: color, color: '#fff', padding: '2px 8px',
        borderRadius: 12, fontSize: 11, fontWeight: 600,
      }}>
        {agent}
      </span>
      <span style={{ fontSize: 13, color: '#94a3b8', marginLeft: 8 }}>
        working...
      </span>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function ConversationFeed() {
  const [inputMessage, setInputMessage] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [activeAgents, setActiveAgents] = useState<Record<string, string>>({});
  const [attachments, setAttachments] = useState<Array<{ eventId: string; filename: string; content: string }>>([]);
  const [showClosed, setShowClosed] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  const { data: activeEvents } = useActiveEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(20),
    refetchOnWindowFocus: true,
  });
  const { data: selectedEvent } = useEventDocument(selectedEventId);
  const { data: archEvents } = useEvents();
  const { invalidateActive, invalidateEvent } = useQueueInvalidation();

  // WebSocket connection
  const { connected, reconnecting, send } = useWebSocket((msg) => {
    if (msg.type === 'turn' || msg.type === 'event_created' || msg.type === 'event_closed') {
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
      if (msg.type === 'turn') {
        const turn = msg.turn as Record<string, unknown>;
        if (turn?.actor) {
          setActiveAgents((prev) => {
            const next = { ...prev };
            delete next[turn.actor as string];
            return next;
          });
        }
      }
    } else if (msg.type === 'progress') {
      setActiveAgents((prev) => ({
        ...prev,
        [msg.actor as string]: msg.message as string,
      }));
    } else if (msg.type === 'attachment') {
      setAttachments((prev) => [...prev.slice(-10), {
        eventId: msg.event_id as string,
        filename: msg.filename as string,
        content: msg.content as string,
      }]);
    }
  });

  const { sendMessage, isPending } = useChat(connected ? send : undefined);

  // Auto-scroll on new content
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [selectedEvent?.conversation?.length, Object.keys(activeAgents).length]);

  const handleSend = () => {
    if (!inputMessage.trim()) return;
    sendMessage(inputMessage);
    setInputMessage('');
  };

  // Combine active + closed for the events panel
  const allEvents = [
    ...(activeEvents || []),
    ...(showClosed ? (closedEvents || []) : []),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Reconnect banner */}
      {reconnecting && (
        <div style={{
          background: '#92400e', color: '#fef3c7', padding: '4px 12px',
          fontSize: 12, textAlign: 'center',
        }}>
          Reconnecting to Brain...
        </div>
      )}

      {/* Connection status bar */}
      <div style={{
        padding: '4px 12px', fontSize: 11, display: 'flex', justifyContent: 'space-between',
        color: connected ? '#4ade80' : '#f87171',
        borderBottom: '1px solid #333',
      }}>
        <span>{connected ? 'Live' : 'Disconnected'}</span>
        <span style={{ color: '#64748b' }}>
          {activeEvents?.length || 0} active
        </span>
      </div>

      {/* ================================================================ */}
      {/* Events Panel - scrollable card list with status indicators       */}
      {/* ================================================================ */}
      <div style={{
        borderBottom: '1px solid #333', maxHeight: 240, overflow: 'auto',
        flexShrink: 0,
      }}>
        <div style={{
          padding: '8px 12px 4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          position: 'sticky', top: 0, background: '#0f172a', zIndex: 1,
        }}>
          <h3 style={{ margin: 0, fontSize: 13, color: '#e2e8f0' }}>Events</h3>
          <button
            onClick={() => setShowClosed(!showClosed)}
            style={{
              background: 'none', border: '1px solid #334155', borderRadius: 4,
              color: '#94a3b8', fontSize: 10, padding: '2px 8px', cursor: 'pointer',
            }}
          >
            {showClosed ? 'Hide Closed' : 'Show Closed'}
          </button>
        </div>
        <div style={{ padding: '4px 12px 8px' }}>
          {allEvents.map((evt: Record<string, unknown>) => (
            <EventCard
              key={evt.id as string}
              evt={evt}
              selected={selectedEventId === evt.id}
              onClick={() => setSelectedEventId(evt.id as string)}
            />
          ))}
          {allEvents.length === 0 && (
            <p style={{ color: '#666', fontSize: 13, padding: '8px 0' }}>No events</p>
          )}
        </div>
      </div>

      {/* ================================================================ */}
      {/* Conversation Stream - sticky header + scrollable turns           */}
      {/* ================================================================ */}
      {selectedEvent ? (
        <>
          {/* Sticky event header */}
          <div style={{
            padding: '8px 12px', borderBottom: '1px solid #333',
            background: '#1e293b', flexShrink: 0,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>
                {selectedEvent.service}
              </span>
              <StatusBadge status={selectedEvent.status} />
              <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                {selectedEvent.id}
              </span>
            </div>
            <span style={{ fontSize: 11, color: '#64748b' }}>
              {selectedEvent.source} | {selectedEvent.conversation.length} turns
            </span>
          </div>

          {/* Scrollable conversation */}
          <div ref={feedRef} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
            {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => (
              <TurnBubble key={i} turn={turn} eventId={selectedEvent.id} />
            ))}
            {/* Attachments for this event */}
            {attachments
              .filter((a) => a.eventId === selectedEventId)
              .map((a, i) => (
                <AttachmentCard key={i} filename={a.filename} content={a.content} />
              ))}
            {/* Active progress indicators */}
            {Object.keys(activeAgents).map((agent) => (
              <ProgressDots key={agent} agent={agent} />
            ))}
          </div>
        </>
      ) : (
        /* No event selected -- show recent activity stream */
        <div ref={feedRef} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
          <p style={{ color: '#64748b', fontSize: 13, marginBottom: 12 }}>
            Select an event above to view the conversation, or send a message below.
          </p>
          {archEvents?.slice(0, 20).map((evt, i) => (
            <div key={i} style={{
              padding: '4px 0', fontSize: 13, color: '#94a3b8',
              borderBottom: '1px solid #1e293b',
            }}>
              <span style={{ color: '#64748b' }}>
                {new Date(evt.timestamp * 1000).toLocaleTimeString()}
              </span>
              {' '}{evt.narrative || evt.type}
            </div>
          ))}
        </div>
      )}

      {/* ================================================================ */}
      {/* Chat Input                                                       */}
      {/* ================================================================ */}
      <div style={{ padding: 12, borderTop: '1px solid #333', display: 'flex', gap: 8, flexShrink: 0 }}>
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask the Brain..."
          style={{
            flex: 1, background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: '8px 12px', color: '#e2e8f0', fontSize: 14,
          }}
        />
        <button
          onClick={handleSend}
          disabled={isPending}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
            fontWeight: 600, opacity: isPending ? 0.5 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default ConversationFeed;
