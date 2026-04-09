// BlackBoard/ui/src/components/ConversationFeed.tsx
// @ai-rules:
// 1. [Pattern]: Pure conversation viewer -- receives eventId as prop from EventSidebar (or Dashboard legacy).
// 2. [Pattern]: WS ownership: owns brain_thinking, brain_thinking_done, message_status, attachment.
// 3. [Pattern]: Report button fetches server-side report via getEventReport(); falls back to client-side eventToMarkdown on failure.
// 4. [Constraint]: closeEvent via REST, not WS -- ensures request completes even if WS is flaky.
// 5. [Pattern]: TurnBubble and MarkdownViewer extracted to own files (transparency compliance refactor).
import { useState, useEffect, useRef, useCallback } from 'react';
import { useEventDocument, useQueueInvalidation } from '../hooks/useQueue';
import { useWSMessage } from '../contexts/WebSocketContext';
import { closeEvent, getEventReport } from '../api/client';
import type { ConversationTurn } from '../api/types';
import TurnBubble, { StatusBadge } from './TurnBubble';
import MarkdownViewer from './MarkdownViewer';
import SourceIcon from './SourceIcon';
import { DOMAIN_COLORS, SEVERITY_COLORS } from '../constants/colors';

function eventToMarkdown(event: { id: string; source: string; status: string; service: string; event: { reason: string; evidence: unknown; timeDate: string }; conversation: ConversationTurn[] }): string {
  const evidence = event.event.evidence;
  const evidenceText = typeof evidence === 'string' ? evidence : (evidence as Record<string, string>)?.display_text || '';
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
  onOpenContentTile?: (title: string, content: string) => void;
}

export function ConversationFeed({ eventId, onInvalidateActive, onClose, onOpenContentTile }: ConversationFeedProps) {
  const [brainThinking, setBrainThinking] = useState<{ eventId: string; text: string; isThought: boolean } | null>(null);
  const [attachments, setAttachments] = useState<Array<{ eventId: string; filename: string; content: string }>>([]);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportContent, setReportContent] = useState<string>('');
  const [turnViewer, setTurnViewer] = useState<{ content: string; filename: string } | null>(null);
  const [userScrolled, setUserScrolled] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  const { data: selectedEvent, isError: eventError } = useEventDocument(eventId);
  const { invalidateActive, invalidateEvent } = useQueueInvalidation();

  const handleFeedScroll = useCallback(() => {
    const el = feedRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setUserScrolled(!atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
      setUserScrolled(false);
    }
  }, []);

  useWSMessage((msg) => {
    if (msg.type === 'brain_thinking') {
      setBrainThinking({
        eventId: msg.event_id as string,
        text: msg.accumulated as string,
        isThought: (msg.is_thought as boolean) || false,
      });
    } else if (msg.type === 'brain_thinking_done') {
      setBrainThinking(null);
    } else if (msg.type === 'message_status' || msg.type === 'domain_updated') {
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
    if (feedRef.current && !userScrolled) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [selectedEvent?.conversation?.length, userScrolled]);

  if (eventError) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444', fontSize: 13 }}>
        Failed to load event conversation.
      </div>
    );
  }
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
      {/* Sticky event header -- two rows */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #333', background: '#1e293b', flexShrink: 0 }}>
        {/* Row 1: identity */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {onClose && (
              <button onClick={onClose}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '2px 4px', fontSize: 16, lineHeight: 1, display: 'flex', alignItems: 'center' }}
                title="Back to Activity">←</button>
            )}
            <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{selectedEvent.service}</span>
            <StatusBadge status={selectedEvent.status} />
            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>{selectedEvent.id}</span>
            {selectedEvent.event?.evidence?.triggered_by && (
              <span style={{ fontSize: 11, color: '#93c5fd', fontWeight: 500 }}>{selectedEvent.event.evidence.triggered_by}</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <SourceIcon source={selectedEvent.source} size={14} />
            <span style={{ fontSize: 11, color: '#64748b' }}>{selectedEvent.source} | {selectedEvent.conversation.length} turns</span>
          </div>
        </div>
        {/* Row 2: actions + metadata pills */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            onClick={async () => {
              let md: string;
              try { const data = await getEventReport(selectedEvent.id); md = data.markdown; }
              catch { md = eventToMarkdown(selectedEvent); }
              if (onOpenContentTile) {
                onOpenContentTile(`Report: ${selectedEvent.id.slice(0, 12)}`, md);
              } else {
                setReportContent(md);
                setReportOpen(true);
              }
            }}
            style={{ background: '#1e3a5f', border: '1px solid #2563eb44', borderRadius: 4, color: '#93c5fd', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
            title="View event report"
          >Report</button>
          {selectedEvent.status === 'waiting_approval' && (
            <button
              onClick={() => handleStatusChange()}
              style={{ background: '#14532d', border: '1px solid #22c55e44', borderRadius: 4, color: '#86efac', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
              title="Approve plan"
            >Approve</button>
          )}
          {selectedEvent.status !== 'closed' && (
            <button
              onClick={() => {
                if (window.confirm(`Force-close event ${selectedEvent.id}?\nThis will stop all Brain processing.`)) {
                  closeEvent(selectedEvent.id).then(() => handleStatusChange());
                }
              }}
              style={{ background: '#7f1d1d', border: '1px solid #dc262644', borderRadius: 4, color: '#fca5a5', fontSize: 12, padding: '3px 10px', cursor: 'pointer', fontWeight: 600 }}
              title="Force close"
            >Force Close</button>
          )}
          <div style={{ flex: 1 }} />
          {(() => {
            const ev = selectedEvent.event?.evidence;
            if (!ev || typeof ev === 'string') return null;
            const domain = ev.brain_domain || ev.domain || 'disorder';
            const dc = DOMAIN_COLORS[domain as keyof typeof DOMAIN_COLORS] || DOMAIN_COLORS.disorder;
            const severity = ev.brain_severity || ev.severity || 'info';
            const sc = SEVERITY_COLORS[severity] || SEVERITY_COLORS.info;
            return (
              <>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, fontWeight: 600, background: dc.bg, color: dc.text, border: `1px solid ${dc.border}30` }}>{domain}</span>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, fontWeight: 600, background: sc.bg, color: sc.text }}>{severity}</span>
              </>
            );
          })()}
        </div>
      </div>

      {reportOpen && <MarkdownViewer filename={`event-${selectedEvent.id}.md`} content={reportContent} onClose={() => setReportOpen(false)} />}
      {turnViewer && <MarkdownViewer filename={turnViewer.filename} content={turnViewer.content} onClose={() => setTurnViewer(null)} />}

      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        <div ref={feedRef} onScroll={handleFeedScroll} style={{ position: 'absolute', inset: 0, overflow: 'auto', padding: 12, ...(selectedEvent.conversation.length > 3 ? { maskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)', WebkitMaskImage: 'linear-gradient(to bottom, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)' } : {}) }}>
          {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => {
            const turnAttachment = (turn.actor === 'brain' && turn.action === 'route')
              ? attachments.find((a) => a.eventId === eventId)
              : null;
            return (
              <TurnBubble key={i} turn={turn} eventId={selectedEvent.id} attachment={turnAttachment} onStatusChange={handleStatusChange} onViewReport={(content, filename) => {
                if (onOpenContentTile) {
                  onOpenContentTile(filename, content);
                } else {
                  setTurnViewer({ content, filename });
                }
              }} />
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
        {userScrolled && (
          <button onClick={scrollToBottom}
            style={{
              position: 'absolute', bottom: 12, left: '50%', transform: 'translateX(-50%)',
              background: '#1e40af', color: '#93c5fd', border: '1px solid #3b82f633',
              borderRadius: 20, padding: '4px 14px', fontSize: 11, fontWeight: 600,
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              boxShadow: '0 4px 12px rgba(0,0,0,0.4)', zIndex: 5,
            }}>
            &#x25BC; Jump to latest
          </button>
        )}
      </div>
    </div>
  );
}

export default ConversationFeed;
