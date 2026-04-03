// BlackBoard/ui/src/components/ChatInput.tsx
// @ai-rules:
// 1. [Pattern]: Dual send path -- WS user_message when eventId provided, REST createChatEvent otherwise.
// 2. [Pattern]: Image paste via clipboard -> resizeImage -> pendingImage state.
// 3. [Constraint]: wsSend is optional; falls back to useChat REST when not available.
/**
 * Event-aware chat input with image paste support.
 * Handles both "reply to event" (WS) and "create new event" (REST) modes.
 */
import { useState, useEffect, useCallback, useRef, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChat } from '../hooks';
import { resizeImage } from '../utils/imageResize';

interface ChatInputProps {
  eventId?: string | null;
  wsSend?: (msg: object) => void;
}

const MIN_INPUT_HEIGHT = 80;
const MAX_INPUT_HEIGHT = 400;
const DEFAULT_INPUT_HEIGHT = 120;

function ChatInput({ eventId, wsSend }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const { sendMessage, isPending } = useChat(wsSend);
  const [formHeight, setFormHeight] = useState(DEFAULT_INPUT_HEIGHT);
  const [isResizing, setIsResizing] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!message.trim() && !pendingImage) return;
    if (eventId && wsSend) {
      wsSend({
        type: 'user_message',
        event_id: eventId,
        message: message.trim(),
        ...(pendingImage ? { image: pendingImage } : {}),
      });
    } else {
      sendMessage(message.trim(), undefined, pendingImage || undefined);
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

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      if (!formRef.current) return;
      const rect = formRef.current.getBoundingClientRect();
      const newH = rect.bottom - e.clientY;
      setFormHeight(Math.min(MAX_INPUT_HEIGHT, Math.max(MIN_INPUT_HEIGHT, newH)));
    };
    const onUp = () => setIsResizing(false);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  return (
    <form ref={formRef} onSubmit={handleSubmit} style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', height: formHeight }}>
      {/* Top-edge resize handle (drag up to expand) */}
      <div className={`flex-shrink-0 flex items-center justify-center cursor-row-resize group ${isResizing ? 'bg-accent/20' : ''}`}
        style={{ height: 6, borderTop: '1px solid #334155' }}
        onMouseDown={startResize}>
        <div className={`h-0.5 w-12 rounded-full transition-colors ${isResizing ? 'bg-accent' : 'bg-border group-hover:bg-accent/60'}`} />
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '6px 12px 12px' }}>
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
