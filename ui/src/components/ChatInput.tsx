// BlackBoard/ui/src/components/ChatInput.tsx
/**
 * Compact chat input for sending messages to the Brain.
 * Uses useChat hook which routes via WebSocket when available.
 */
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChat } from '../hooks';

function ChatInput() {
  const [message, setMessage] = useState('');
  const { sendMessage, isPending } = useChat();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!message.trim() || isPending) return;
    sendMessage(message.trim());
    setMessage('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-3 border-t border-border">
      <div className="flex gap-2">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask the Brain..."
          rows={1}
          className="flex-1 px-3 py-2 bg-bg-primary border border-border rounded-lg text-sm text-text-primary placeholder-text-muted resize-none focus:outline-none focus:border-border-focus"
          disabled={isPending}
        />
        <button
          type="submit"
          disabled={!message.trim() || isPending}
          className="px-3 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
