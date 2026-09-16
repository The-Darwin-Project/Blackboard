// BlackBoard/ui/src/components/ChatInput.tsx
// @ai-rules:
// 1. [Pattern]: Dual send path -- WS user_message when connected, REST otherwise. eventId is always
//    threaded through so the REST fallback appends to the selected event instead of creating a new one.
// 2. [Pattern]: Image paste via clipboard -> resizeImage -> pendingImage state.
// 3. [Constraint]: wsSend is optional; falls back to useChat REST when not available.
// 4. [Pattern]: Per-event draft isolation via draftsRef Map<string, Draft>. On eventId change,
//    saves current message and image to the old event's draft and restores the new event's draft
//    (or empty if none). The save-and-restore runs synchronously in one effect after eventId commits.
// 5. [Pattern]: Step 9 resilience -- captures lastSubmissionRef on send, listens to WS error envelopes
//    via useWSMessage, restores draft non-clobbering on error, and renders dismissible alert banner.
/**
 * Event-aware chat input with image paste support and resilient error feedback.
 * Handles both "reply to event" (WS) and "create new event" (REST) modes.
 */
import { useState, useEffect, useRef, useCallback, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2, AlertCircle, X } from 'lucide-react';
import { useChat } from '../hooks';
import { useResizablePanel } from '../hooks/useResizablePanel';
import { resizeImage } from '../utils/imageResize';
import { useWSMessage } from '../contexts/WebSocketContext';

interface ChatInputProps {
  eventId?: string | null;
  wsSend?: (msg: object) => void;
}

interface Draft {
  text: string;
  image: string | null;
}

interface LastSubmission {
  text: string;
  image: string | null;
  eventId: string | null;
  timestamp: number;
}

const MIN_INPUT_HEIGHT = 80;
const MAX_INPUT_HEIGHT = 400;
const DEFAULT_INPUT_HEIGHT = 120;

function ChatInput({ eventId, wsSend }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { sendMessage, isPending } = useChat(wsSend);
  const draftsRef = useRef<Map<string, Draft>>(new Map());
  const prevEventIdRef = useRef<string | null | undefined>(eventId);
  const lastSubmissionRef = useRef<LastSubmission | null>(null);

  // Per-event draft isolation: save draft for old event, restore for new event
  useEffect(() => {
    const prevId = prevEventIdRef.current;
    if (prevId === eventId) return;

    // Save current message & image as draft for the previous event
    if (prevId) {
      const currentMsg = message.trim();
      if (currentMsg || pendingImage) {
        draftsRef.current.set(prevId, { text: currentMsg, image: pendingImage });
      } else {
        draftsRef.current.delete(prevId);
      }
    }

    // Restore draft for the new event (or empty if no draft saved)
    const draft = eventId ? draftsRef.current.get(eventId) : null;
    setMessage(draft?.text ?? '');
    setPendingImage(draft?.image ?? null);
    setErrorMessage(null);
    prevEventIdRef.current = eventId;
  }, [eventId]); // eslint-disable-line react-hooks/exhaustive-deps -- message & pendingImage read intentionally excluded

  // Listen for WS error envelopes (Step 9)
  useWSMessage(useCallback((msg) => {
    if (msg.type !== 'error') return;
    // Guard by event_id if present
    if (msg.event_id && msg.event_id !== eventId) return;

    console.warn('[ChatInput] Received error envelope:', msg);
    const errText = typeof msg.message === 'string' ? msg.message : 'Message rejected by server';
    setErrorMessage(errText);

    // Non-clobbering draft restore from lastSubmissionRef
    const lastSub = lastSubmissionRef.current;
    if (lastSub && (!lastSub.eventId || lastSub.eventId === eventId)) {
      setMessage((cur) => cur.trim() ? cur : lastSub.text);
      setPendingImage((cur) => cur ? cur : lastSub.image);
    }
  }, [eventId]));

  const { size: formHeight, isResizing, startResize, panelRef: formRef } = useResizablePanel<HTMLFormElement>({
    direction: 'vertical', min: MIN_INPUT_HEIGHT, max: MAX_INPUT_HEIGHT, defaultSize: DEFAULT_INPUT_HEIGHT,
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = message.trim();
    if (!trimmed && !pendingImage) return;

    // Record last submission for potential rollback on WS error
    lastSubmissionRef.current = {
      text: trimmed,
      image: pendingImage,
      eventId: eventId || null,
      timestamp: Date.now(),
    };

    // Clear saved draft for this event upon submission
    if (eventId) {
      draftsRef.current.delete(eventId);
    }
    setErrorMessage(null);

    if (eventId && wsSend) {
      wsSend({
        type: 'user_message',
        event_id: eventId,
        message: trimmed,
        ...(pendingImage ? { image: pendingImage } : {}),
      });
    } else {
      sendMessage(trimmed, undefined, pendingImage || undefined, eventId || undefined);
    }
    setMessage('');
    setPendingImage(null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (!file) continue;
        resizeImage(file, 1024, 1_400_000).then((dataUrl) => {
          if (dataUrl) setPendingImage(dataUrl);
          else alert('Image too large even after resize.');
        });
        e.preventDefault();
        break;
      }
    }
  };


  return (
    <form ref={formRef} onSubmit={handleSubmit} style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', height: formHeight }}>
      {/* Top-edge resize handle (drag up to expand) */}
      <div className={`flex-shrink-0 flex items-center justify-center cursor-row-resize group ${isResizing ? 'bg-accent/20' : ''}`}
        style={{ height: 6, borderTop: '1px solid #334155' }}
        onMouseDown={startResize}>
        <div className={`h-0.5 w-12 rounded-full transition-colors ${isResizing ? 'bg-accent' : 'bg-border group-hover:bg-accent/60'}`} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '6px 12px 12px' }}>
        {/* Error Alert Banner */}
        {errorMessage && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 10px', marginBottom: 6, borderRadius: 6,
            background: '#ef444415', border: '1px solid #ef444440',
            color: '#f87171', fontSize: 12, flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="truncate">{errorMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', padding: '0 4px', display: 'flex', alignItems: 'center' }}
              aria-label="Dismiss error"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Event context indicator */}
        {eventId && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexShrink: 0,
            padding: '4px 10px', borderRadius: 6,
            background: '#3b82f615', border: '1px solid #3b82f630',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3b82f6', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: '#93c5fd', fontWeight: 600 }}>Replying to</span>
            <span style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace' }}>{eventId.slice(0, 16)}</span>
          </div>
        )}
        {/* Image preview */}
        {pendingImage && (
          <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <img src={pendingImage} alt="Attached" style={{ maxHeight: 50, maxWidth: 120, borderRadius: 6, border: '1px solid #334155' }} />
            <button type="button" onClick={() => setPendingImage(null)} aria-label="Remove image"
              style={{ background: '#334155', border: 'none', color: '#94a3b8', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}>
              Remove
            </button>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, flex: 1, minHeight: 0 }}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={eventId ? 'Reply to event... (Ctrl+V to paste screenshot)' : 'Ask the Brain...'}
            style={{
              flex: 1, background: '#1e293b', border: '1px solid #334155',
              borderRadius: 8, padding: '8px 12px', color: '#e2e8f0', fontSize: 14,
              resize: 'none', overflow: 'auto',
              fontFamily: 'inherit', lineHeight: '1.4',
            }}
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={(!message.trim() && !pendingImage) || isPending}
            style={{
              background: '#3b82f6', color: '#fff', border: 'none',
              padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
              opacity: isPending ? 0.5 : 1, display: 'flex', alignItems: 'center',
              justifyContent: 'center', alignSelf: 'flex-end',
            }}
            title="Send (Enter)"
          >
            {isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

export default ChatInput;
