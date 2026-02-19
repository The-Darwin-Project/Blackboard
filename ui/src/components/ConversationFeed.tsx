// BlackBoard/ui/src/components/ConversationFeed.tsx
// @ai-rules:
// 1. [Pattern]: Pure conversation viewer -- receives eventId as prop from Dashboard.
// 2. [Pattern]: WS ownership: owns brain_thinking, brain_thinking_done, message_status, attachment.
// 3. [Pattern]: Report button fetches server-side report via getEventReport(); falls back to client-side eventToMarkdown on failure.
// 4. [Constraint]: closeEvent via REST, not WS -- ensures request completes even if WS is flaky.
// 5. [Pattern]: TurnBubble and MarkdownViewer extracted to own files (transparency compliance refactor).
import { useState, useEffect, useRef } from 'react';
import { useEventDocument, useQueueInvalidation } from '../hooks/useQueue';
import { useWSMessage } from '../contexts/WebSocketContext';
import { closeEvent, getEventReport } from '../api/client';
import type { ConversationTurn } from '../api/types';
import TurnBubble, { StatusBadge } from './TurnBubble';
import MarkdownViewer from './MarkdownViewer';

function eventToMarkdown(event: { id: string; source: string; status: string; service: string; event: { reason: string; evidence: any; timeDate: string }; conversation: ConversationTurn[] }): string {
  const evidenceText = typeof event.event.evidence === 'string' ? event.event.evidence : event.event.evidence?.display_text || '';
  const lines: string[] = [
    `# Event: ${event.id}`, '',
    `- **Source:** ${event.source}`, `- **Service:** ${event.service}`,
    `- **Status:** ${event.status}`, `- **Reason:** ${event.event.reason}`,
    `- **Evidence:** ${evidenceText}`, `- **Time:** ${event.event.timeDate}`,
    '', '## Conversation', '',
  ];
  let prevTs = event.conversation[0]?.timestamp || 0;
  for (const turn of event.conversation) {
    const ts = new Date(turn.timestamp * 1000).toLocaleTimeString('en-GB', { hour12: false });
    const delta = Math.round(turn.timestamp - prevTs);
    const deltaLabel = delta > 0 ? `+${Math.floor(delta / 60)}m ${delta % 60}s` : '+0s';
    lines.push(`### Turn ${turn.turn} - ${turn.actor} (${turn.action}) [${ts}] (${deltaLabel})`);
    prevTs = turn.timestamp;
    if (turn.thoughts) lines.push(`**Thoughts:** ${turn.thoughts}`);
    if (turn.result) lines.push(`**Result:** ${turn.result}`);
    if (turn.plan) lines.push(`**Plan:**\n${turn.plan}`);
    if (turn.evidence) lines.push(`**Evidence:** ${turn.evidence}`);
    if (turn.selectedAgents) lines.push(`**Selected Agents:** ${turn.selectedAgents.join(', ')}`);
    if (turn.pendingApproval) lines.push('**Pending Approval:** YES');
    if (turn.waitingFor) lines.push(`**Waiting For:** ${turn.waitingFor}`);
    lines.push('');
  }
  return lines.join('\n');
}

interface ConversationFeedProps {
  eventId: string;
  onInvalidateActive: () => void;
  onClose?: () => void;
}

export function ConversationFeed({ eventId, onInvalidateActive, onClose }: ConversationFeedProps) {
  const [brainThinking, setBrainThinking] = useState<{ eventId: string; text: string; isThought: boolean } | null>(null);
  const [attachments, setAttachments] = useState<Array<{ eventId: string; filename: string; content: string }>>([]);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportContent, setReportContent] = useState<string>('');
  const feedRef = useRef<HTMLDivElement>(null);

  const { data: selectedEvent } = useEventDocument(eventId);
  const { invalidateActive, invalidateEvent } = useQueueInvalidation();

  useWSMessage((msg) => {
    if (msg.type === 'brain_thinking') {
      setBrainThinking({
        eventId: msg.event_id as string,
        text: msg.accumulated as string,
        isThought: (msg.is_thought as boolean) || false,
      });
    } else if (msg.type === 'brain_thinking_done') {
      setBrainThinking(null);
    } else if (msg.type === 'message_status') {
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'attachment') {
      setAttachments((prev) => {
        const filtered = prev.filter((a) => a.eventId !== (msg.event_id as string));
        return [...filtered.slice(-9), {
          eventId: msg.event_id as string,
          filename: msg.filename as string,
          content: msg.content as string,
        }];
      });
    }
  });

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [selectedEvent?.conversation?.length]);

  if (!selectedEvent) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: 13 }}>
        Loading event...
      </div>
    );
  }

  const handleStatusChange = () => {
    invalidateActive();
    invalidateEvent(selectedEvent.id);
    onInvalidateActive();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
      {/* Sticky event header */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #333', background: '#1e293b', flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {onClose && (
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px 4px', fontSize: 16, lineHeight: 1, display: 'flex', alignItems: 'center' }}
              title="Back to Activity"
            >←</button>
          )}
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{selectedEvent.service}</span>
          <StatusBadge status={selectedEvent.status} />
          <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>{selectedEvent.id}</span>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#64748b' }}>{selectedEvent.source} | {selectedEvent.conversation.length} turns</span>
          <button
            onClick={async () => {
              try { const data = await getEventReport(selectedEvent.id); setReportContent(data.markdown); }
              catch { setReportContent(eventToMarkdown(selectedEvent)); }
              setReportOpen(true);
            }}
            style={{ background: '#1e3a5f', border: '1px solid #2563eb44', borderRadius: 4, color: '#93c5fd', fontSize: 11, padding: '2px 8px', cursor: 'pointer', fontWeight: 600 }}
            title="View event report"
          >Report</button>
          {selectedEvent.status !== 'closed' && (
            <button
              onClick={() => {
                if (window.confirm(`Force-close event ${selectedEvent.id}?\nThis will stop all Brain processing.`)) {
                  closeEvent(selectedEvent.id).then(() => handleStatusChange());
                }
              }}
              style={{ background: '#7f1d1d', border: '1px solid #dc262644', borderRadius: 4, color: '#fca5a5', fontSize: 11, padding: '2px 8px', cursor: 'pointer', fontWeight: 600 }}
              title="Force close"
            >Force Close</button>
          )}
        </div>
      </div>

      {reportOpen && <MarkdownViewer filename={`event-${selectedEvent.id}.md`} content={reportContent} onClose={() => setReportOpen(false)} />}

      <div ref={feedRef} style={{ flex: 1, overflow: 'auto', padding: 12, minHeight: 0, ...(selectedEvent.conversation.length > 3 ? { maskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)', WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)' } : {}) }}>
        {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => {
          const turnAttachment = (turn.actor === 'brain' && turn.action === 'route')
            ? attachments.find((a) => a.eventId === eventId)
            : null;
          return (
            <TurnBubble key={i} turn={turn} eventId={selectedEvent.id} attachment={turnAttachment} onStatusChange={handleStatusChange} />
          );
        })}
        {brainThinking && brainThinking.eventId === eventId && (
          <div style={{ padding: '8px 12px', margin: '4px 0', borderLeft: `3px solid ${brainThinking.isThought ? '#8b5cf6' : '#3b82f6'}`, background: brainThinking.isThought ? '#7c3aed10' : '#1e3a5f15', borderRadius: 4, fontSize: 13, color: '#94a3b8', fontStyle: 'italic', animation: 'pulse 2s infinite' }}>
            <span style={{ color: brainThinking.isThought ? '#8b5cf6' : '#3b82f6', fontWeight: 600, fontSize: 11 }}>
              {brainThinking.isThought ? 'Brain reasoning...' : 'Brain thinking...'}
            </span>
            <p style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{brainThinking.text}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ConversationFeed;
