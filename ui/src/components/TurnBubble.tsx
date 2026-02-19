// BlackBoard/ui/src/components/TurnBubble.tsx
// @ai-rules:
// 1. [Pattern]: Receives ConversationTurn + eventId + attachment. Pure display component.
// 2. [Pattern]: AI-generated badge shown for all non-user turns (transparency compliance).
// 3. [Pattern]: StatusBadge is exported for use in ConversationFeed event header.
// 4. [Gotcha]: Transient errors (429, 503) rendered as "Brain retrying..." with spinner, not full bubble.
import { useState } from 'react';
import { approveEvent, rejectEvent, submitFeedback } from '../api/client';
import type { ConversationTurn, MessageStatus } from '../api/types';
import { ACTOR_COLORS, STATUS_COLORS } from '../constants/colors';
import { resizeImage } from '../utils/imageResize';
import { RefreshCw } from 'lucide-react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import { getCodeString } from 'rehype-rewrite';
import MermaidBlock from './MermaidBlock';
import MarkdownViewer from './MarkdownViewer';

export function StatusBadge({ status }: { status: string }) {
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
        <MarkdownPreview source={devExpanded ? devText : devText.slice(0, PREVIEW_LEN) + (!devExpanded && devText.length > PREVIEW_LEN ? '\n...' : '')} style={{ fontSize: 13, background: 'transparent', color: '#e2e8f0' }} wrapperElement={{ 'data-color-mode': 'dark' }} />
        {devText.length > PREVIEW_LEN && <button onClick={() => setDevExpanded(!devExpanded)} style={{ background: '#22c55e22', color: '#22c55e', border: '1px solid #22c55e44', padding: '2px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', marginTop: 4 }}>{devExpanded ? 'Collapse' : 'View full'}</button>}
      </div>
      <div style={{ padding: '8px 12px', borderLeft: '3px solid #8b5cf6', background: 'rgba(168, 85, 247, 0.06)', borderRadius: 4 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: '#8b5cf6', marginBottom: 4 }}>QE ASSESSMENT</div>
        <MarkdownPreview source={qeExpanded ? qeText : qeText.slice(0, PREVIEW_LEN) + (!qeExpanded && qeText.length > PREVIEW_LEN ? '\n...' : '')} style={{ fontSize: 13, background: 'transparent', color: '#e2e8f0' }} wrapperElement={{ 'data-color-mode': 'dark' }} />
        {qeText.length > PREVIEW_LEN && <button onClick={() => setQeExpanded(!qeExpanded)} style={{ background: '#8b5cf622', color: '#8b5cf6', border: '1px solid #8b5cf644', padding: '2px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', marginTop: 4 }}>{qeExpanded ? 'Collapse' : 'View full'}</button>}
      </div>
    </div>
  );
}

function ResultViewer({ result }: { result: string }) {
  return (
    <div style={{ margin: '4px 0' }}>
      <MarkdownPreview source={result} style={{ fontSize: 13, background: 'transparent', color: '#e2e8f0', lineHeight: 1.6 }} wrapperElement={{ 'data-color-mode': 'dark' }} components={{ code: ({ children, className, ...props }) => { const code = props.node?.children ? getCodeString(props.node.children) : String(children ?? ''); if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLowerCase())) return <MermaidBlock code={code} />; return <code className={String(className ?? '')}>{children}</code>; } }} />
    </div>
  );
}

function StatusCheck({ status }: { status?: MessageStatus }) {
  if (!status || status === 'sent') return <span title="Sent" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓</span>;
  if (status === 'delivered') return <span title="Delivered" style={{ fontSize: 11, color: '#64748b', marginLeft: 4 }}>✓✓</span>;
  return <span title="Evaluated" style={{ fontSize: 11, color: '#3b82f6', marginLeft: 4 }}>✓✓</span>;
}

function FeedbackButtons({ eventId, turnNumber }: { eventId: string; turnNumber: number }) {
  const [submitted, setSubmitted] = useState<'positive' | 'negative' | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');

  if (submitted) {
    return <span style={{ fontSize: 11, color: '#64748b', marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 4 }}>✓ Thanks</span>;
  }

  const handleSubmit = (rating: 'positive' | 'negative', text?: string) => {
    setSubmitted(rating);
    setShowComment(false);
    submitFeedback(eventId, turnNumber, rating, text).catch(() => setSubmitted(null));
  };

  return (
    <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        <button onClick={() => handleSubmit('positive')} title="Helpful" style={{ background: 'none', border: '1px solid #334155', borderRadius: 4, padding: '2px 6px', cursor: 'pointer', fontSize: 13, color: '#94a3b8', lineHeight: 1 }}>👍</button>
        <button onClick={() => setShowComment(true)} title="Not helpful" style={{ background: 'none', border: '1px solid #334155', borderRadius: 4, padding: '2px 6px', cursor: 'pointer', fontSize: 13, color: '#94a3b8', lineHeight: 1 }}>👎</button>
      </div>
      {showComment && (
        <div style={{ display: 'flex', gap: 4, alignItems: 'flex-start' }}>
          <input value={comment} onChange={(e) => setComment(e.target.value.slice(0, 500))} placeholder="What went wrong?" style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 4, padding: '3px 6px', color: '#e2e8f0', fontSize: 12, flex: 1, maxWidth: 280 }} />
          <button onClick={() => handleSubmit('negative', comment)} style={{ background: '#334155', border: 'none', borderRadius: 4, padding: '3px 8px', color: '#e2e8f0', fontSize: 11, cursor: 'pointer', whiteSpace: 'nowrap' }}>Send</button>
        </div>
      )}
    </div>
  );
}

export default function TurnBubble({ turn, eventId, attachment, onStatusChange }: {
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
        <span style={{ background: color, color: '#fff', padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>{turn.user_name ? `${turn.actor} (${turn.user_name})` : turn.actor}</span>
        {!isHuman && <span style={{ fontSize: 10, color: '#94a3b8', background: '#334155', padding: '1px 6px', borderRadius: 8, fontWeight: 500 }}>AI-generated</span>}
        {!isHuman && turn.actor !== 'brain' && <StatusCheck status={turn.status} />}
        {!isHuman && attachment && <AttachmentIcon filename={attachment.filename} content={attachment.content} />}
      </div>
      {turn.thoughts && <MarkdownPreview source={turn.thoughts} style={{ margin: '4px 0', fontSize: 14, background: 'transparent', color: '#e2e8f0' }} wrapperElement={{ 'data-color-mode': 'dark' }} />}
      {turn.image && (
        <img src={turn.image} alt="User attachment" style={{ maxWidth: 400, maxHeight: 300, borderRadius: 8, border: '1px solid #334155', marginTop: 4, cursor: 'pointer', ...(isHuman ? { marginLeft: 'auto', display: 'block' } : {}) }} onClick={(e) => window.open((e.target as HTMLImageElement).src, '_blank')} />
      )}
      {turn.result && (
        turn.actor === 'developer' && turn.result.includes('## Developer Result') && turn.result.includes('## QE Assessment') ? (
          <HuddleResultViewer result={turn.result} />
        ) : turn.action === 'execute' && turn.result.length > 500 ? (
          <ResultViewer result={turn.result} />
        ) : (
          <MarkdownPreview source={turn.result} style={{ margin: '4px 0', fontSize: 14, background: 'transparent', color: '#4ade80' }} wrapperElement={{ 'data-color-mode': 'dark' }} />
        )
      )}
      {turn.plan && <MarkdownPreview source={turn.plan} style={{ background: '#1e1e2e', padding: 12, borderRadius: 8, fontSize: 13, overflow: 'auto', maxHeight: 300, color: '#e2e8f0' }} wrapperElement={{ 'data-color-mode': 'dark' }} components={{ code: ({ children, className, ...props }) => { const code = props.node?.children ? getCodeString(props.node.children) : String(children ?? ''); if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLowerCase())) return <MermaidBlock code={code} />; return <code className={String(className ?? '')}>{children}</code>; } }} />}
      {turn.evidence && <p style={{ margin: '4px 0', fontSize: 13, color: '#94a3b8' }}>Evidence: {turn.evidence}</p>}
      {turn.pendingApproval && eventId && (
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button onClick={() => approveEvent(eventId).then(() => onStatusChange?.())} style={{ background: '#22c55e', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>Approve</button>
          <RejectButton eventId={eventId!} onStatusChange={onStatusChange} />
        </div>
      )}
      {!isHuman && eventId && <FeedbackButtons eventId={eventId} turnNumber={turn.turn} />}
    </div>
  );
}
