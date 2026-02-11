// BlackBoard/ui/src/components/ConversationFeed.tsx
// @ai-rules:
// 1. [Pattern]: selectedEventId persisted in sessionStorage -- survives page refresh.
// 2. [Pattern]: useWSReconnect invalidates all queries to catch missed WS messages.
// 3. [Pattern]: Report button fetches server-side report via getEventReport(); falls back to client-side eventToMarkdown on failure.
// 4. [Constraint]: closeEvent via REST, not WS -- ensures request completes even if WS is flaky.
// 5. [Pattern]: MarkdownViewer uses @uiw/react-markdown-preview with custom MermaidBlock for fenced mermaid code blocks.
// 6. [Gotcha]: mermaid.initialize() called once at module scope -- NOT inside useEffect. MermaidBlock only calls mermaid.render().
/**
 * Unified group-chat view with real-time WebSocket updates.
 * Layout: Events panel (top) + Conversation stream (bottom) + Chat input
 */
import { useState, useEffect, useRef } from 'react';
import { useActiveEvents, useEventDocument, useQueueInvalidation } from '../hooks/useQueue';
import { useEvents } from '../hooks/useEvents';
import { useChat } from '../hooks/useChat';
import { useWSConnection, useWSMessage, useWSReconnect } from '../contexts/WebSocketContext';
import { approveEvent, rejectEvent, closeEvent, getClosedEvents, getEventReport } from '../api/client';
import type { ConversationTurn, MessageStatus } from '../api/types';
import { useQuery } from '@tanstack/react-query';
import { ACTOR_COLORS, STATUS_COLORS } from '../constants/colors';
import { resizeImage } from '../utils/imageResize';
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
  filename,
  content,
  onClose,
}: {
  filename: string;
  content: string;
  onClose: () => void;
}) {
  const [maximized, setMaximized] = useState(false);
  const [size, setSize] = useState({ width: 600, height: 450 });
  const [pos, setPos] = useState({ x: 100, y: 60 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  // Drag handler
  const onDragStart = (e: React.MouseEvent) => {
    if (maximized) return;
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setPos({
        x: dragRef.current.origX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.origY + (ev.clientY - dragRef.current.startY),
      });
    };
    const onUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  // Resize handler
  const onResizeStart = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (maximized) return;
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: size.width, origH: size.height };
    const onMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      setSize({
        width: Math.max(300, resizeRef.current.origW + (ev.clientX - resizeRef.current.startX)),
        height: Math.max(200, resizeRef.current.origH + (ev.clientY - resizeRef.current.startY)),
      });
    };
    const onUp = () => {
      resizeRef.current = null;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };


  const windowStyle: React.CSSProperties = maximized
    ? { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1000 }
    : { position: 'fixed', top: pos.y, left: pos.x, width: size.width, height: size.height, zIndex: 1000 };

  return (
    <>
      {/* Backdrop */}
      <div
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 999 }}
        onClick={onClose}
      />
      {/* Window */}
      <div style={{
        ...windowStyle,
        background: '#0f172a', border: '1px solid #334155', borderRadius: maximized ? 0 : 8,
        display: 'flex', flexDirection: 'column', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
      }}>
        {/* Title bar */}
        <div
          onMouseDown={onDragStart}
          style={{
            padding: '8px 12px', background: '#1e293b', borderBottom: '1px solid #334155',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            cursor: maximized ? 'default' : 'move', borderRadius: maximized ? 0 : '8px 8px 0 0',
            flexShrink: 0, userSelect: 'none',
          }}
        >
          <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{filename}</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => setMaximized(!maximized)}
              style={{
                background: '#334155', border: 'none', borderRadius: 4, color: '#94a3b8',
                width: 24, height: 24, cursor: 'pointer', fontSize: 12,
              }}
              title={maximized ? 'Restore' : 'Maximize'}
            >
              {maximized ? '◱' : '◳'}
            </button>
            <button
              onClick={onClose}
              style={{
                background: '#dc2626', border: 'none', borderRadius: 4, color: '#fff',
                width: 24, height: 24, cursor: 'pointer', fontSize: 12, fontWeight: 700,
              }}
              title="Close"
            >
              x
            </button>
          </div>
        </div>
        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          <MarkdownPreview
            source={content}
            style={{ padding: 16, background: 'transparent', fontSize: 13, lineHeight: 1.6 }}
            wrapperElement={{ 'data-color-mode': 'dark' }}
            components={{
              code: ({ children, className, ...props }) => {
                const code = props.node?.children
                  ? getCodeString(props.node.children)
                  : (Array.isArray(children) ? String(children[0] ?? '') : String(children ?? ''));
                if (typeof code === 'string' && typeof className === 'string'
                    && /^language-mermaid/.test(className.toLowerCase())) {
                  return <MermaidBlock code={code} />;
                }
                return <code className={String(className ?? '')}>{children}</code>;
              },
            }}
          />
        </div>
        {/* Resize handle */}
        {!maximized && (
          <div
            onMouseDown={onResizeStart}
            style={{
              position: 'absolute', bottom: 0, right: 0, width: 16, height: 16,
              cursor: 'nwse-resize', opacity: 0.5,
            }}
          >
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M14 14L8 14L14 8Z" fill="#64748b" />
            </svg>
          </div>
        )}
      </div>
    </>
  );
}

/** Attachment icon shown inline in Brain turn bubbles */
function AttachmentIcon({
  filename,
  content,
}: {
  filename: string;
  content: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <span
        onClick={() => setOpen(true)}
        title={filename}
        style={{
          cursor: 'pointer', marginLeft: 6, display: 'inline-flex',
          alignItems: 'center', verticalAlign: 'middle',
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.8 }}>
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
        </svg>
      </span>
      {open && (
        <MarkdownViewer filename={filename} content={content} onClose={() => setOpen(false)} />
      )}
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
      <button
        onClick={() => setShowModal(true)}
        style={{
          background: '#ef4444', color: '#fff', border: 'none',
          padding: '6px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 600,
        }}
      >
        Reject
      </button>
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#1e293b', borderRadius: 12, padding: 20, width: 480,
            border: '1px solid #334155', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          }}>
            <h3 style={{ color: '#e2e8f0', margin: '0 0 12px', fontSize: 16 }}>Reject Plan</h3>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              onPaste={handleRejectPaste}
              placeholder="Reason for rejection... (Ctrl+V to paste screenshot)"
              rows={3}
              style={{
                width: '100%', background: '#0f172a', border: '1px solid #334155',
                borderRadius: 8, padding: 10, color: '#e2e8f0', fontSize: 14,
                resize: 'vertical', fontFamily: 'inherit',
              }}
            />
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

/** Collapsible viewer for long agent execute results */
function ResultViewer({ actor, result }: { actor: string; result: string }) {
  const [expanded, setExpanded] = useState(false);
  const color = ACTOR_COLORS[actor] || '#6b7280';
  return (
    <div style={{ margin: '4px 0' }}>
      <p style={{ fontSize: 14, color: '#4ade80' }}>
        {result.slice(0, 150)}...
      </p>
      <button
        onClick={() => setExpanded(true)}
        style={{
          background: `${color}22`, color, border: `1px solid ${color}44`,
          padding: '3px 12px', borderRadius: 6, fontSize: 12,
          cursor: 'pointer', marginTop: 4,
        }}
      >
        View full response
      </button>
      {expanded && (
        <MarkdownViewer
          filename={`${actor}-response.md`}
          content={result}
          onClose={() => setExpanded(false)}
        />
      )}
    </div>
  );
}

/** Message status indicator: single check (sent), double check (delivered), blue double check (evaluated) */
function StatusCheck({ status }: { status?: MessageStatus }) {
  if (!status || status === 'sent') {
    return <span title="Sent" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓</span>;
  }
  if (status === 'delivered') {
    return <span title="Delivered" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓✓</span>;
  }
  // evaluated
  return <span title="Evaluated" style={{ fontSize: 11, color: '#3b82f6', marginLeft: 4 }}>✓✓</span>;
}

function TurnBubble({
  turn,
  eventId,
  attachment,
  onStatusChange,
}: {
  turn: ConversationTurn;
  eventId?: string;
  attachment?: { filename: string; content: string } | null;
  onStatusChange?: () => void;
}) {
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
        {turn.actor !== 'brain' && <StatusCheck status={turn.status} />}
        {attachment && (
          <AttachmentIcon filename={attachment.filename} content={attachment.content} />
        )}
      </div>
      {turn.thoughts && <p style={{ margin: '4px 0', fontSize: 14, color: '#e2e8f0' }}>{turn.thoughts}</p>}
      {turn.image && (
        <img
          src={turn.image}
          alt="User attachment"
          style={{ maxWidth: 400, maxHeight: 300, borderRadius: 8, border: '1px solid #334155', marginTop: 4, cursor: 'pointer' }}
          onClick={(e) => window.open((e.target as HTMLImageElement).src, '_blank')}
        />
      )}
      {turn.result && (
        // Developer huddle result: split into Dev + QE sections
        turn.actor === 'developer' && turn.result.includes('## Developer Result') && turn.result.includes('## QE Assessment') ? (
          <div style={{ margin: '4px 0' }}>
            {turn.result.split('## QE Assessment').map((section, idx) => (
              <div key={idx} style={{
                padding: '8px 12px',
                borderLeft: `3px solid ${idx === 0 ? '#22c55e' : '#8b5cf6'}`,
                marginBottom: idx === 0 ? 8 : 0,
                background: idx === 0 ? 'rgba(16, 185, 129, 0.06)' : 'rgba(168, 85, 247, 0.06)',
                borderRadius: 4,
              }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: idx === 0 ? '#22c55e' : '#8b5cf6', marginBottom: 4 }}>
                  {idx === 0 ? 'DEVELOPER' : 'QE ASSESSMENT'}
                </div>
                <div style={{ fontSize: 13, color: '#e2e8f0', whiteSpace: 'pre-wrap' }}>
                  {(idx === 0 ? section.replace('## Developer Result', '').trim() : section.trim()).slice(0, 2000)}
                </div>
              </div>
            ))}
          </div>
        ) : turn.action === 'execute' && turn.result.length > 500 ? (
          <ResultViewer actor={turn.actor} result={turn.result} />
        ) : (
          <p style={{ margin: '4px 0', fontSize: 14, color: '#4ade80' }}>{turn.result}</p>
        )
      )}
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
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button
            onClick={() => approveEvent(eventId).then(() => onStatusChange?.())}
            style={{
              background: '#22c55e', color: '#fff', border: 'none',
              padding: '6px 16px', borderRadius: 6, cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Approve
          </button>
          <RejectButton eventId={eventId!} onStatusChange={onStatusChange} />
        </div>
      )}
    </div>
  );
}

// ProgressDots removed -- replaced by AgentStreamCard in Dashboard

// ============================================================================
// Main Component
// ============================================================================

/** Convert an EventDocument to readable Markdown (client-side mirror of Brain._event_to_markdown). */
function eventToMarkdown(event: { id: string; source: string; status: string; service: string; event: { reason: string; evidence: string; timeDate: string }; conversation: ConversationTurn[] }): string {
  const lines: string[] = [
    `# Event: ${event.id}`,
    '',
    `- **Source:** ${event.source}`,
    `- **Service:** ${event.service}`,
    `- **Status:** ${event.status}`,
    `- **Reason:** ${event.event.reason}`,
    `- **Evidence:** ${event.event.evidence}`,
    `- **Time:** ${event.event.timeDate}`,
    '',
    '## Conversation',
    '',
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

const SESSION_KEY = 'darwin:selectedEventId';

export function ConversationFeed() {
  const [inputMessage, setInputMessage] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(
    () => sessionStorage.getItem(SESSION_KEY),
  );
  const [activeAgents, setActiveAgents] = useState<Record<string, string>>({});
  const [attachments, setAttachments] = useState<Array<{ eventId: string; filename: string; content: string }>>([]);
  const [showClosed, setShowClosed] = useState(false);
  const [pendingImage, setPendingImage] = useState<string | null>(null); // base64 data URI
  const [reportOpen, setReportOpen] = useState(false); // Event report markdown viewer
  const [reportContent, setReportContent] = useState<string>(''); // Server-side report markdown
  const feedRef = useRef<HTMLDivElement>(null);

  // Persist selected event across page refreshes
  useEffect(() => {
    if (selectedEventId) sessionStorage.setItem(SESSION_KEY, selectedEventId);
    else sessionStorage.removeItem(SESSION_KEY);
  }, [selectedEventId]);

  const { data: activeEvents } = useActiveEvents();
  const { data: closedEvents } = useQuery({
    queryKey: ['closedEvents'],
    queryFn: () => getClosedEvents(20),
    refetchOnWindowFocus: true,
    refetchInterval: 10000, // Check for newly closed events every 10s
  });
  const { data: selectedEvent, isError: selectedEventError } = useEventDocument(selectedEventId);

  // Auto-clear stale event selection (e.g., event cleaned up after pod restart)
  useEffect(() => {
    if (selectedEventError && selectedEventId) {
      sessionStorage.removeItem(SESSION_KEY);
      setSelectedEventId(null);
    }
  }, [selectedEventError, selectedEventId]);
  const { data: archEvents } = useEvents();
  const { invalidateActive, invalidateEvent, invalidateAll } = useQueueInvalidation();

  // WebSocket connection (from shared context provider)
  const { connected, reconnecting, send } = useWSConnection();
  useWSMessage((msg) => {
    if (msg.type === 'turn' || msg.type === 'event_created' || msg.type === 'event_closed') {
      invalidateActive();
      if (msg.event_id) invalidateEvent(msg.event_id as string);
      // Auto-select newly created events from chat
      if (msg.type === 'event_created' && msg.event_id) {
        setSelectedEventId(msg.event_id as string);
      }
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
    } else if (msg.type === 'message_status') {
      // Status update for turns (delivered/evaluated) -- invalidate to refresh
      if (msg.event_id) invalidateEvent(msg.event_id as string);
    } else if (msg.type === 'attachment') {
      // Replace attachment per event (always show latest version)
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

  // On WS reconnect, invalidate all cached queries to catch turns/closures
  // that arrived during the disconnect gap.
  useWSReconnect(() => {
    invalidateAll();
  });

  const { sendMessage, isPending } = useChat(connected ? send : undefined);

  // Auto-scroll on new content
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [selectedEvent?.conversation?.length, Object.keys(activeAgents).length]);

  const handleSend = () => {
    if (!inputMessage.trim() && !pendingImage) return;
    if (selectedEventId && connected) {
      send({
        type: 'user_message',
        event_id: selectedEventId,
        message: inputMessage.trim(),
        ...(pendingImage ? { image: pendingImage } : {}),
      });
    } else {
      sendMessage(inputMessage, undefined, pendingImage || undefined);
    }
    setInputMessage('');
    setPendingImage(null);
  };

  // Handle image paste from clipboard (with resize)
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (!file) continue;
        resizeImage(file, 1024, 1_400_000).then((dataUrl) => {
          if (dataUrl) {
            setPendingImage(dataUrl);
          } else {
            alert('Image too large even after resize. Try a smaller screenshot.');
          }
        });
        e.preventDefault();
        break;
      }
    }
  };

  // Combine active + recently closed (always show last 5 min) + older closed (toggle)
  const recentClosed = (closedEvents || []).filter((evt: Record<string, unknown>) => {
    // Show events closed in last 5 minutes regardless of toggle
    const created = evt.created as string;
    if (!created) return false;
    const age = Date.now() - new Date(created).getTime();
    return age < 30 * 60 * 1000;
  });
  const olderClosed = (closedEvents || []).filter((evt: Record<string, unknown>) => {
    const created = evt.created as string;
    if (!created) return true;
    const age = Date.now() - new Date(created).getTime();
    return age >= 30 * 60 * 1000;
  });
  const allEvents = [
    ...(activeEvents || []),
    ...recentClosed,
    ...(showClosed ? olderClosed : []),
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
            {showClosed ? `Hide Closed (${closedEvents?.length || 0})` : `Show Closed (${closedEvents?.length || 0})`}
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
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: '#64748b' }}>
                {selectedEvent.source} | {selectedEvent.conversation.length} turns
              </span>
              {/* Report button -- fetches full event report from server */}
              <button
                onClick={async () => {
                  try {
                    const data = await getEventReport(selectedEvent.id);
                    setReportContent(data.markdown);
                  } catch {
                    // Fallback to client-side if API fails
                    setReportContent(eventToMarkdown(selectedEvent));
                  }
                  setReportOpen(true);
                }}
                style={{
                  background: '#1e3a5f', border: '1px solid #2563eb44',
                  borderRadius: 4, color: '#93c5fd', fontSize: 11,
                  padding: '2px 8px', cursor: 'pointer', fontWeight: 600,
                }}
                title="View event report"
              >
                Report
              </button>
              {/* Force close -- only for non-closed events */}
              {selectedEvent.status !== 'closed' && (
                <button
                  onClick={() => {
                    if (window.confirm(`Force-close event ${selectedEvent.id}?\nThis will stop all Brain processing for this event.`)) {
                      closeEvent(selectedEvent.id).then(() => {
                        invalidateActive();
                        invalidateEvent(selectedEvent.id);
                      });
                    }
                  }}
                  style={{
                    background: '#7f1d1d', border: '1px solid #dc262644',
                    borderRadius: 4, color: '#fca5a5', fontSize: 11,
                    padding: '2px 8px', cursor: 'pointer', fontWeight: 600,
                  }}
                  title="Force close this event"
                >
                  Force Close
                </button>
              )}
              <button
                onClick={() => setSelectedEventId(null)}
                style={{
                  background: '#334155', border: 'none', borderRadius: 4,
                  color: '#94a3b8', fontSize: 14, padding: '2px 8px',
                  cursor: 'pointer', lineHeight: 1,
                }}
                title="Close conversation"
              >
                x
              </button>
            </div>
          </div>

          {/* Event report markdown viewer (server-side with fallback) */}
          {reportOpen && (
            <MarkdownViewer
              filename={`event-${selectedEvent.id}.md`}
              content={reportContent}
              onClose={() => setReportOpen(false)}
            />
          )}

          {/* Scrollable conversation */}
          <div ref={feedRef} style={{ flex: 1, overflow: 'auto', padding: 12 }}>
            {selectedEvent.conversation.map((turn: ConversationTurn, i: number) => {
              // Find attachment for this turn (Brain route turns have attachments)
              const turnAttachment = (turn.actor === 'brain' && turn.action === 'route')
                ? attachments.find((a) => a.eventId === selectedEventId)
                : null;
              return (
                <TurnBubble
                  key={i}
                  turn={turn}
                  eventId={selectedEvent.id}
                  attachment={turnAttachment}
                  onStatusChange={() => {
                    invalidateActive();
                    invalidateEvent(selectedEvent.id);
                  }}
                />
              );
            })}
            {/* Agent progress now shown in AgentStreamCards in Dashboard */}
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
      <div style={{ padding: 12, borderTop: '1px solid #333', flexShrink: 0 }}>
        {/* Image preview */}
        {pendingImage && (
          <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <img src={pendingImage} alt="Attached" style={{ maxHeight: 80, maxWidth: 200, borderRadius: 6, border: '1px solid #334155' }} />
            <button
              onClick={() => setPendingImage(null)}
              style={{ background: '#334155', border: 'none', color: '#94a3b8', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 12 }}
            >
              Remove
            </button>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            onPaste={handlePaste}
            placeholder="Ask the Brain... (Ctrl+V to paste screenshot)"
            rows={3}
            style={{
              flex: 1, background: '#1e293b', border: '1px solid #334155',
              borderRadius: 8, padding: '8px 12px', color: '#e2e8f0', fontSize: 14,
              resize: 'vertical', minHeight: 60, maxHeight: 200, overflow: 'auto',
              fontFamily: 'inherit', lineHeight: '1.4',
            }}
          />
          <button
            onClick={handleSend}
            disabled={isPending}
            style={{
              background: '#3b82f6', color: '#fff', border: 'none',
              padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
              opacity: isPending ? 0.5 : 1, display: 'flex', alignItems: 'center',
              justifyContent: 'center', alignSelf: 'flex-end',
            }}
            title="Send (Enter)"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConversationFeed;
