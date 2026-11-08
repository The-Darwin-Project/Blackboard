// BlackBoard/ui/src/components/AgentStreamCard.tsx
// @ai-rules:
// 1. [Pattern]: All agents (permanent + oncall) use the same card layout with agent-colored left border.
// 2. [Pattern]: FloatingWindow provides pop-out view for any agent stream.
// 3. [Constraint]: Color falls back to green (#4ade80) for oncall agents not in ACTOR_COLORS.
/**
 * Real-time streaming card for agent CLI output.
 * Each agent (architect, sysadmin, developer, qe) gets its own independent card.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { ACTOR_COLORS } from '../constants/colors';
import { FloatingWindow } from './workspace/FloatingWindow';
import { sanitizeClipboardText } from './workspace/CopyButton';

interface AgentStreamCardProps {
  agentName: string;
  eventId: string | null;
  messages: string[];
  isActive: boolean;
}

/** Render agent messages as individual bubbles (matching brain turn style). */
function MessageCards({ messages, color }: { messages: string[]; color: string }) {
  if (messages.length === 0) {
    return <div style={{ color: '#334155', fontStyle: 'italic', fontSize: 11 }}>Idle</div>;
  }
  return (
    <>
      {messages.slice(-50).map((line, i) => (
        <div key={i} style={{
          marginBottom: 4,
          padding: '4px 10px',
          borderRadius: 8,
          borderLeft: `3px solid ${color}`,
          background: `${color}12`,
          fontSize: 12,
          fontFamily: 'monospace',
          lineHeight: '1.4',
          wordBreak: 'break-word' as const,
          whiteSpace: 'pre-wrap' as const,
          color: '#94a3b8',
        }}>
          {line}
        </div>
      ))}
    </>
  );
}

export default function AgentStreamCard({ agentName, eventId, messages, isActive }: AgentStreamCardProps) {
  const color = ACTOR_COLORS[agentName] || '#4ade80';
  const scrollRef = useRef<HTMLDivElement>(null);
  const [poppedOut, setPoppedOut] = useState(false);
  const [userScrolled, setUserScrolled] = useState(false);

  useEffect(() => {
    if (scrollRef.current && !userScrolled) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, userScrolled]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setUserScrolled(!atBottom);
  }, []);

  return (
    <>
      <div style={{
        flex: 1, minWidth: 0, minHeight: 0, background: '#0f172a',
        borderRadius: 8, border: `1px solid ${isActive ? color : '#334155'}`,
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        opacity: isActive ? 1 : 0.6, transition: 'opacity 0.3s, border-color 0.3s',
      }}>
        {/* Header */}
        <div style={{
          padding: '6px 10px', borderBottom: `1px solid ${isActive ? color + '33' : '#1e293b'}`,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
            <span style={{ background: color, color: '#fff', padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
              {agentName}
            </span>
            <span style={{ flex: 1, textAlign: 'center' }}>
              {eventId && <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>[{eventId.slice(0, 12)}]</span>}
              {isActive && <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block', marginLeft: 4 }} />}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 3 }}>
            <button
              onClick={() => {
                if (messages.length > 0) {
                  const sanitized = sanitizeClipboardText(messages.join('\n'));
                  navigator.clipboard?.writeText(sanitized).catch(() => {});
                }
              }}
              title="Copy stream"
              aria-label="Copy stream"
              className="hover:bg-white/10 hover:border-white/20 transition-colors"
              style={{
                background: `${color}08`, border: `1px solid ${color}25`, color: '#94a3b8',
                cursor: 'pointer', padding: 0, borderRadius: 5,
                width: 28, height: 28, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <Copy size={13} />
            </button>
            <button
              onClick={() => setPoppedOut(true)}
              title="Pop out"
              aria-label="Pop out"
              className="hover:bg-white/10 hover:border-white/20 transition-colors"
              style={{
                background: `${color}08`, border: `1px solid ${color}25`, color: '#94a3b8',
                cursor: 'pointer', padding: 0, borderRadius: 5,
                width: 28, height: 28, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <ExternalLink size={13} />
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div ref={scrollRef} onScroll={handleScroll} style={{
          flex: 1, minHeight: 0, overflow: 'auto', padding: '6px 10px', fontFamily: 'monospace',
          fontSize: 12, lineHeight: '1.4', color: '#94a3b8',
        }}>
          <MessageCards messages={messages} color={color} />
        </div>
      </div>

      {/* Floating window */}
      {poppedOut && (
        <FloatingWindow
          agentName={agentName} eventId={eventId}
          messages={messages}
          onClose={() => setPoppedOut(false)}
        />
      )}
    </>
  );
}
