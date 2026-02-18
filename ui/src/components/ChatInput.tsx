// BlackBoard/ui/src/components/ChatInput.tsx
// @ai-rules:
// 1. [Pattern]: Dual send path -- WS user_message when eventId provided, REST createChatEvent otherwise.
// 2. [Pattern]: Image paste via clipboard -> resizeImage -> pendingImage state.
// 3. [Constraint]: wsSend is optional; falls back to useChat REST when not available.
/**
 * Event-aware chat input with image paste support.
 * Handles both "reply to event" (WS) and "create new event" (REST) modes.
 */
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChat } from '../hooks';
import { resizeImage } from '../utils/imageResize';

interface ChatInputProps {
  eventId?: string | null;
  wsSend?: (msg: object) => void;
}

function ChatInput({ eventId, wsSend }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [pendingImage, setPendingImage] = useState<string | null>(null);
  const { sendMessage, isPending } = useChat(wsSend);

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

  return (
    <form onSubmit={handleSubmit} style={{ padding: 12, borderTop: '1px solid #334155', flexShrink: 0 }}>
      {/* Image preview */}
      {pendingImage && (
        <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <img src={pendingImage} alt="Attached" style={{ maxHeight: 60, maxWidth: 150, borderRadius: 6, border: '1px solid #334155' }} />
          <button
            type="button"
            onClick={() => setPendingImage(null)}
            aria-label="Remove image"
            style={{ background: '#334155', border: 'none', color: '#94a3b8', borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11 }}
          >
            Remove
          </button>
        </div>
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={eventId ? 'Reply to event... (Ctrl+V to paste screenshot)' : 'Ask the Brain...'}
          rows={3}
          style={{
            flex: 1, background: '#1e293b', border: '1px solid #334155',
            borderRadius: 8, padding: '8px 12px', color: '#e2e8f0', fontSize: 14,
            resize: 'vertical', minHeight: 60, maxHeight: 200, overflow: 'auto',
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
    </form>
  );
}

export default ChatInput;
