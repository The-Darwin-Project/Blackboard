// BlackBoard/ui/src/components/ConversationFeed.tsx
// @ai-rules:
// 1. [Pattern]: Pure conversation viewer -- receives eventId as prop from Dashboard.
// 2. [Pattern]: WS ownership: owns brain_thinking, brain_thinking_done, message_status, attachment.
// 3. [Pattern]: Report button fetches server-side report via getEventReport(); falls back to client-side eventToMarkdown on failure.
// 4. [Constraint]: closeEvent via REST, not WS -- ensures request completes even if WS is flaky.
// 5. [Pattern]: MarkdownViewer uses @uiw/react-markdown-preview with custom MermaidBlock for fenced mermaid code blocks.
// 6. [Gotcha]: mermaid.initialize() called once at module scope -- NOT inside useEffect. MermaidBlock only calls mermaid.render().
/**
 * Pure conversation viewer for a selected event.
 * Displays: event header, scrollable turn bubbles, brain thinking indicator, report viewer.
 * Chat input, event list, and activity stream have been extracted to separate components.
 */
import { useState, useEffect, useRef } from 'react';
import { useEventDocument, useQueueInvalidation } from '../hooks/useQueue';
import { useWSMessage } from '../contexts/WebSocketContext';
import { approveEvent, rejectEvent, closeEvent, getEventReport } from '../api/client';
import type { ConversationTurn, MessageStatus } from '../api/types';
import { ACTOR_COLORS, STATUS_COLORS } from '../constants/colors';
import { resizeImage } from '../utils/imageResize';
import { RefreshCw } from 'lucide-react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import mermaid from 'mermaid';
import { getCodeString } from 'rehype-rewrite';

// Initialize mermaid once at module scope (not per-render)
mermaid.initialize({ startOnLoad: false, theme: 'dark' });

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

/** Renders a single Mermaid diagram inside MarkdownPreview */
function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2, 8)}`);

  useEffect(() => {
    if (ref.current) {
      mermaid.render(idRef.current, code).then(({ svg }) => {
        if (ref.current) ref.current.innerHTML = svg;
      }).catch((err) => {
        if (ref.current) ref.current.textContent = String(err);
      });
    }
  }, [code]);

  return <div ref={ref} style={{ display: 'flex', justifyContent: 'center', padding: '8px 0' }} />;
}

/** Floating resizable Markdown preview window */
function MarkdownViewer({
  filename, content, onClose,
}: {
  filename: string; content: string; onClose: () => void;
}) {
  const [maximized, setMaximized] = useState(false);
  const [size, setSize] = useState({ width: 600, height: 450 });
  const [pos, setPos] = useState({ x: 100, y: 60 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  const onDragStart = (e: React.MouseEvent) => {
    if (maximized) return;
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setPos({ x: dragRef.current.origX + (ev.clientX - dragRef.current.startX), y: dragRef.current.origY + (ev.clientY - dragRef.current.startY) });
    };
    const onUp = () => { dragRef.current = null; document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  const onResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (maximized) return;
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: size.width, origH: size.height };
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      setSize({ width: Math.max(300, resizeRef.current.origW + (ev.clientX - resizeRef.current.startX)), height: Math.max(200, resizeRef.current.origH + (ev.clientY - resizeRef.current.startY)) });
    };
    const onUp = () => { resizeRef.current = null; document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  const windowStyle: React.CSSProperties = maximized
    ? { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1000 }
    : { position: 'fixed', top: pos.y, left: pos.x, width: size.width, height: size.height, zIndex: 1000 };

  return (
    <>
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 999 }} onClick={onClose} />
      <div style={{ ...windowStyle, background: '#0f172a', border: '1px solid #334155', borderRadius: maximized ? 0 : 8, display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
        <div onMouseDown={onDragStart} style={{ padding: '8px 12px', background: '#1e293b', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: maximized ? 'default' : 'move', borderRadius: maximized ? 0 : '8px 8px 0 0', flexShrink: 0, userSelect: 'none' }}>
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{filename}</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => setMaximized(!maximized)} style={{ background: '#334155', border: 'none', borderRadius: 4, color: '#94a3b8', width: 24, height: 24, cursor: 'pointer', fontSize: 12 }} title={maximized ? 'Restore' : 'Maximize'}>{maximized ? '◱' : '◳'}</button>
            <button onClick={onClose} style={{ background: '#dc2626', border: 'none', borderRadius: 4, color: '#fff', width: 24, height: 24, cursor: 'pointer', fontSize: 12, fontWeight: 700 }} title="Close">x</button>
          </div>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <MarkdownPreview source={content} style={{ padding: 16, background: 'transparent', fontSize: 13, lineHeight: 1.6 }} wrapperElement={{ 'data-color-mode': 'dark' }} components={{
            code: ({ children, className, ...props }) => {
              const code = props.node?.children ? getCodeString(props.node.children) : (Array.isArray(children) ? String(children[0] ?? '') : String(children ?? ''));
              if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLowerCase())) return <MermaidBlock code={code} />;
              return <code className={String(className ?? '')}>{children}</code>;
            },
          }} />
        </div>
        {!maximized && (
          <div onMouseDown={onResizeStart} style={{ position: 'absolute', bottom: 0, right: 0, width: 16, height: 16, cursor: 'nwse-resize', opacity: 0.5 }}>
            <svg width="16" height="16" viewBox="0 0 16 16"><path d="M14 14L8 14L14 8Z" fill="#64748b" /></svg>
          </div>
        )}
      </div>
    </>
  );
}

/** Attachment icon shown inline in Brain turn bubbles */
function AttachmentIcon({ filename, content }: { filename: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <span onClick={() => setOpen(true)} title={filename} style={{ cursor: 'pointer', marginLeft: 6, display: 'inline-flex', alignItems: 'center', verticalAlign: 'middle' }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.8 }}>
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
        </svg>
      </span>
      {open && <MarkdownViewer filename={filename} content={content} onClose={() => setOpen(false)} />}
    </>
  );
}

/** Reject button with modal supporting text + image attachment */
function RejectButton({ eventId, onStatusChange }: { eventId: string; onStatusChange?: () => void }) {
  const [showModal, setShowModal] = useState(false);
  const [reason, setReason] = useState('');
  const [rejectImage, setRejectImage] = useState<string | null>(null);

  const handleRejectPaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (!file) continue;
        resizeImage(file, 1024, 1_400_000).then((dataUrl) => {
          if (dataUrl) setRejectImage(dataUrl);
          else alert('Image too large even after resize.');
        });
        e.preventDefault();
        break;
      }
    }
  };

  const handleSubmit = () => {
    const finalReason = reason.trim() || 'User rejected the plan.';
    rejectEvent(eventId, finalReason, rejectImage || undefined).then(() => {
      onStatusChange?.();
      setShowModal(false);
      setReason('');
      setRejectImage(null);
    });
  };

  return (
    <>
      <button onClick={() => setShowModal(true)} style={{ background: '#ef4444', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>Reject</button>
      {showModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, width: 480, border: '1px solid #334155', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
            <h3 style={{ color: '#e2e8f0', margin: '0 0 12px', fontSize: 16 }}>Reject Plan</h3>
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} onPaste={handleRejectPaste} placeholder="Reason for rejection... (Ctrl+V to paste screenshot)" rows={3} style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: 8, padding: 10, color: '#e2e8f0', fontSize: 14, resize: 'vertical', fontFamily: 'inherit' }} />
            {rejectImage && (
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                <img src={rejectImage} alt="Attached" style={{ maxHeight: 60, maxWidth: 150, borderRadius: 4, border: '1px solid #334155' }} />
                <button onClick={() => setRejectImage(null)} style={{ background: '#334155', border: 'none', color: '#94a3b8', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}>Remove</button>
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
              <button onClick={() => { setShowModal(false); setReason(''); setRejectImage(null); }} style={{ background: '#334155', color: '#94a3b8', border: 'none', padding: '6px 16px', borderRadius: 6, cursor: 'pointer' }}>Cancel</button>
              <button onClick={handleSubmit} style={{ background: '#ef4444', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>Reject</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** Huddle result: Dev + QE split view with expand/collapse per section. */
function HuddleResultViewer({ result }: { result: string }) {
  const [devExpanded, setDevExpanded] = useState(false);
  const [qeExpanded, setQeExpanded] = useState(false);
  const parts = result.split('## QE Assessment');
  const devText = (parts[0] || '').replace('## Developer Result', '').trim();
  const qeText = (parts[1] || '').trim();
  const PREVIEW_LEN = 300;

  return (
    <div style={{ margin: '4px 0' }}>
      <div style={{ padding: '8px 12px', borderLeft: '3px solid #22c55e', marginBottom: 8, background: 'rgba(16, 185, 129, 0.06)', borderRadius: 4 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#22c55e', marginBottom: 4 }}>DEVELOPER</div>
        <div style={{ fontSize: 13, color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>{devExpanded ? devText : devText.slice(0, PREVIEW_LEN)}{!devExpanded && devText.length > PREVIEW_LEN ? '...' : ''}</div>
        {devText.length > PREVIEW_LEN && <button onClick={() => setDevExpanded(!devExpanded)} style={{ background: '#22c55e22', color: '#22c55e', border: '1px solid #22c55e44', padding: '2px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', marginTop: 4 }}>{devExpanded ? 'Collapse' : 'View full'}</button>}
      </div>
      <div style={{ padding: '8px 12px', borderLeft: '3px solid #8b5cf6', background: 'rgba(168, 85, 247, 0.06)', borderRadius: 4 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#8b5cf6', marginBottom: 4 }}>QE ASSESSMENT</div>
        <div style={{ fontSize: 13, color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>{qeExpanded ? qeText : qeText.slice(0, PREVIEW_LEN)}{!qeExpanded && qeText.length > PREVIEW_LEN ? '...' : ''}</div>
        {qeText.length > PREVIEW_LEN && <button onClick={() => setQeExpanded(!qeExpanded)} style={{ background: '#8b5cf622', color: '#8b5cf6', border: '1px solid #8b5cf644', padding: '2px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', marginTop: 4 }}>{qeExpanded ? 'Collapse' : 'View full'}</button>}
      </div>
    </div>
  );
}

function ResultViewer({ actor, result }: { actor: string; result: string }) {
  const [expanded, setExpanded] = useState(false);
  const color = ACTOR_COLORS[actor] || '#6b7280';
  return (
    <div style={{ margin: '4px 0' }}>
      <p style={{ fontSize: 14, color: '#4ade80', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{result}</p>
      <button onClick={() => setExpanded(true)} style={{ background: `${color}22`, color, border: `1px solid ${color}44`, padding: '3px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer', marginTop: 4 }}>View as Markdown</button>
      {expanded && <MarkdownViewer filename={`${actor}-response.md`} content={result} onClose={() => setExpanded(false)} />}
    </div>
  );
}

/** Message status indicator */
function StatusCheck({ status }: { status?: MessageStatus }) {
  if (!status || status === 'sent') return <span title="Sent" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓</span>;
  if (status === 'delivered') return <span title="Delivered" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓✓</span>;
  return <span title="Evaluated" style={{ fontSize: 11, color: '#3b82f6', marginLeft: 4 }}>✓✓</span>;
}

function TurnBubble({ turn, eventId, attachment, onStatusChange }: {
  turn: ConversationTurn; eventId?: string;
  attachment?: { filename: string; content: string } | null;
  onStatusChange?: () => void;
}) {
  const color = ACTOR_COLORS[turn.actor] || '#6b7280';
  const isHuman = turn.actor === 'user';
  const isTransientError = turn.action === 'error' && turn.thoughts && (/429|RESOURCE_EXHAUSTED|503|UNAVAILABLE|rate.limit|quota/i.test(turn.thoughts));

  if (isTransientError) {
    return (
      <div style={{ borderLeft: '3px solid #64748b', paddingLeft: 12, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', color: '#64748b', fontSize: 12, fontStyle: 'italic' }}>
        <RefreshCw size={14} className="animate-spin" />
        Brain retrying...
      </div>
    );
  }

  return (
    <div style={{ ...(isHuman ? { borderRight: `3px solid ${color}`, paddingRight: 12, marginLeft: 'auto', maxWidth: '85%', textAlign: 'right' as const } : { borderLeft: `3px solid ${color}`, paddingLeft: 12 }), marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, ...(isHuman ? { justifyContent: 'flex-end' } : {}) }}>
        {isHuman && attachment && <AttachmentIcon filename={attachment.filename} content={attachment.content} />}
        {isHuman && turn.actor !== 'brain' && <StatusCheck status={turn.status} />}
        <span style={{ fontSize: 11, color: '#666' }}>{new Date(turn.timestamp * 1000).toLocaleTimeString()}</span>
        <span style={{ fontSize: 12, color: '#888' }}>{turn.action}</span>
        <span style={{ background: color, color: '#fff', padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>{turn.actor}</span>
        {!isHuman && turn.actor !== 'brain' && <StatusCheck status={turn.status} />}
        {!isHuman && attachment && <AttachmentIcon filename={attachment.filename} content={attachment.content} />}
      </div>
      {turn.thoughts && <p style={{ margin: '4px 0', fontSize: 14, color: '#e2e8f0' }}>{turn.thoughts}</p>}
      {turn.image && (
        <img src={turn.image} alt="User attachment" style={{ maxWidth: 400, maxHeight: 300, borderRadius: 8, border: '1px solid #334155', marginTop: 4, cursor: 'pointer', ...(isHuman ? { marginLeft: 'auto', display: 'block' } : {}) }} onClick={(e) => window.open((e.target as HTMLImageElement).src, '_blank')} />
      )}
      {turn.result && (
        turn.actor === 'developer' && turn.result.includes('## Developer Result') && turn.result.includes('## QE Assessment') ? (
          <HuddleResultViewer result={turn.result} />
        ) : turn.action === 'execute' && turn.result.length > 500 ? (
          <ResultViewer actor={turn.actor} result={turn.result} />
        ) : (
          <p style={{ margin: '4px 0', fontSize: 14, color: '#4ade80' }}>{turn.result}</p>
        )
      )}
      {turn.plan && <pre style={{ background: '#1e1e2e', padding: 12, borderRadius: 8, fontSize: 13, overflow: 'auto', maxHeight: 300, color: '#e2e8f0' }}>{turn.plan}</pre>}
      {turn.evidence && <p style={{ margin: '4px 0', fontSize: 13, color: '#94a3b8' }}>Evidence: {turn.evidence}</p>}
      {turn.pendingApproval && eventId && (
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button onClick={() => approveEvent(eventId).then(() => onStatusChange?.())} style={{ background: '#22c55e', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>Approve</button>
          <RejectButton eventId={eventId!} onStatusChange={onStatusChange} />
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/** Convert an EventDocument to readable Markdown (client-side fallback). */
function eventToMarkdown(event: { id: string; source: string; status: string; service: string; event: { reason: string; evidence: any; timeDate: string }; conversation: ConversationTurn[] }): string {
  const evidenceText = typeof event.event.evidence === 'string' ? event.event.evidence : event.event.evidence?.display_text || '';
  const lines: string[] = [
    `# Event: ${event.id}`, '',
    `- **Source:** ${event.source}`, `- **Service:** ${event.service}`,
    `- **Status:** ${event.status}`, `- **Reason:** ${event.event.reason}`,
    `- **Evidence:** ${evidenceText}`, `- **Time:** ${event.event.timeDate}`,
    '', '## Conversation', '',
  ];
  for (const turn of event.conversation) {
    lines.push(`### Turn ${turn.turn} - ${turn.actor} (${turn.action})`);
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
}

export function ConversationFeed({ eventId, onInvalidateActive }: ConversationFeedProps) {
  const [brainThinking, setBrainThinking] = useState<{ eventId: string; text: string; isThought: boolean } | null>(null);
  const [attachments, setAttachments] = useState<Array<{ eventId: string; filename: string; content: string }>>([]);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportContent, setReportContent] = useState<string>('');
  const feedRef = useRef<HTMLDivElement>(null);

  const { data: selectedEvent } = useEventDocument(eventId);
  const { invalidateActive, invalidateEvent } = useQueueInvalidation();

  // WS ownership: brain_thinking, brain_thinking_done, message_status, attachment
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

  // Auto-scroll on new content
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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Sticky event header */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #333', background: '#1e293b', flexShrink: 0, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
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

      {/* Event report viewer */}
      {reportOpen && <MarkdownViewer filename={`event-${selectedEvent.id}.md`} content={reportContent} onClose={() => setReportOpen(false)} />}

      {/* Scrollable conversation */}
      <div ref={feedRef} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => {
          const turnAttachment = (turn.actor === 'brain' && turn.action === 'route')
            ? attachments.find((a) => a.eventId === eventId)
            : null;
          return (
            <TurnBubble key={i} turn={turn} eventId={selectedEvent.id} attachment={turnAttachment} onStatusChange={handleStatusChange} />
          );
        })}
        {/* Brain thinking indicator */}
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
