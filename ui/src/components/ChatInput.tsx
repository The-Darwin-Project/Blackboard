// BlackBoard/ui/src/components/ChatInput.tsx
/**
 * Compact chat input for sending messages to the Brain.
 * Creates events via the new chat mutation.
 */
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { useChat } from '../hooks';

function ChatInput() {
  const [message, setMessage] = useState('');
  const chatMutation = useChat();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!message.trim() || chatMutation.isPending) return;

    chatMutation.mutate(
      { message: message.trim() },
      { onSuccess: () => setMessage('') },
    );
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
          disabled={chatMutation.isPending}
        />
        <button
          type="submit"
          disabled={!message.trim() || chatMutation.isPending}
          className="px-3 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {chatMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>
      {chatMutation.isError && (
        <div className="mt-2 p-2 bg-status-critical/10 border border-status-critical/20 rounded-lg">
          <p className="text-xs text-status-critical">Failed to send message. Please try again.</p>
        </div>
      )}
    </form>
  );
}

export default ChatInput;
