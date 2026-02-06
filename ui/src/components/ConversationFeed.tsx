// BlackBoard/ui/src/components/ConversationFeed.tsx
/**
 * Unified group-chat view for Brain event conversations.
 * Replaces the old AgentFeed with a real-time conversation timeline.
 */
import { useState } from 'react';
import { useActiveEvents, useEventDocument } from '../hooks/useQueue';
import { useEvents } from '../hooks/useEvents';
import { useChat } from '../hooks/useChat';
import { approveEvent } from '../api/client';
import type { ConversationTurn } from '../api/types';

const ACTOR_COLORS: Record<string, string> = {
  brain: '#8b5cf6',
  architect: '#3b82f6',
  sysadmin: '#f59e0b',
  developer: '#10b981',
  aligner: '#6b7280',
  user: '#ec4899',
};

function TurnBubble({ turn }: { turn: ConversationTurn }) {
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
      {turn.thoughts && <p style={{ margin: '4px 0', fontSize: 14 }}>{turn.thoughts}</p>}
      {turn.result && <p style={{ margin: '4px 0', fontSize: 14, color: '#4ade80' }}>{turn.result}</p>}
      {turn.plan && (
        <pre style={{
          background: '#1e1e2e', padding: 12, borderRadius: 8,
          fontSize: 13, overflow: 'auto', maxHeight: 300,
        }}>
          {turn.plan}
        </pre>
      )}
      {turn.evidence && (
        <p style={{ margin: '4px 0', fontSize: 13, color: '#94a3b8' }}>
          Evidence: {turn.evidence}
        </p>
      )}
      {turn.pendingApproval && (
        <button
          onClick={() => {
            const eventEl = document.querySelector('[data-event-id]');
            const eventId = eventEl?.getAttribute('data-event-id');
            if (eventId) approveEvent(eventId);
          }}
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

export function ConversationFeed() {
  const [inputMessage, setInputMessage] = useState('');
  const { data: activeEvents } = useActiveEvents();
  const { data: archEvents } = useEvents();
  const chatMutation = useChat();
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const { data: selectedEvent } = useEventDocument(selectedEventId);

  const handleSend = () => {
    if (!inputMessage.trim()) return;
    chatMutation.mutate({ message: inputMessage });
    setInputMessage('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Active Events List */}
      <div style={{ padding: 12, borderBottom: '1px solid #333' }}>
        <h3 style={{ margin: '0 0 8px 0', fontSize: 14 }}>Active Events</h3>
        {activeEvents?.map((evt: any) => (
          <div
            key={evt.id}
            onClick={() => setSelectedEventId(evt.id)}
            style={{
              padding: '6px 10px', marginBottom: 4, borderRadius: 6,
              background: selectedEventId === evt.id ? '#334155' : '#1e293b',
              cursor: 'pointer', fontSize: 13,
            }}
          >
            <strong>{evt.service}</strong> - {evt.reason?.slice(0, 50)}
            <span style={{ float: 'right', fontSize: 11, color: '#666' }}>
              {evt.turns} turns
            </span>
          </div>
        ))}
        {(!activeEvents || activeEvents.length === 0) && (
          <p style={{ color: '#666', fontSize: 13 }}>No active events</p>
        )}
      </div>

      {/* Conversation Timeline */}
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }} data-event-id={selectedEventId}>
        {selectedEvent ? (
          <>
            <div style={{ marginBottom: 12, fontSize: 13, color: '#94a3b8' }}>
              Event: {selectedEvent.id} | {selectedEvent.source} | {selectedEvent.status}
            </div>
            {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => (
              <TurnBubble key={i} turn={turn} />
            ))}
          </>
        ) : (
          /* Show recent architecture events when no event selected */
          <div>
            {archEvents?.slice(0, 20).map((evt: any, i: number) => (
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
      </div>

      {/* Chat Input */}
      <div style={{ padding: 12, borderTop: '1px solid #333', display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask the Brain..."
          style={{
            flex: 1, background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: '8px 12px', color: '#e2e8f0',
            fontSize: 14,
          }}
        />
        <button
          onClick={handleSend}
          disabled={chatMutation.isPending}
          style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
            fontWeight: 600, opacity: chatMutation.isPending ? 0.5 : 1,
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default ConversationFeed;
