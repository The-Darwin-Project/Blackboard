// BlackBoard/ui/src/components/AgentStreamCard.tsx
// @ai-rules:
// 1. [Pattern]: All agents use message card layout with agent-colored left border.
// 2. [Pattern]: Ephemeral (oncall) agents use terminal-style renderer.
// 3. [Pattern]: FloatingWindow provides pop-out view for any agent stream.
// 4. [Constraint]: QE is a first-class agent with its own card (no huddle/pair-programming mode).
/**
 * Real-time streaming card for agent CLI output.
 * Each agent (architect, sysadmin, developer, qe) gets its own independent card.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { ACTOR_COLORS } from '../constants/colors';

interface AgentStreamCardProps {
  agentName: string;
  eventId: string | null;
  messages: string[];
  isActive: boolean;
  ephemeral?: boolean;
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

/** Terminal-style renderer for ephemeral on-call agent streams. */
function TerminalView({ messages, isActive }: { messages: string[]; isActive: boolean }) {
  const startLine = Math.max(0, messages.length - 80);
  if (messages.length === 0) {
    return (
      <div style={{ color: '#4ade8040', fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: 12.5 }}>
        <span style={{ color: '#4ade80' }}>$</span> Waiting for dispatch...
        {isActive && <span className="terminal-cursor" />}
      </div>
    );
  }
  return (
    <>
      {messages.slice(-80).map((line, i) => {
        const lineNum = startLine + i + 1;
        return (
          <div key={i} style={{
            padding: '1px 0',
            fontSize: 12.5,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            lineHeight: '1.55',
            wordBreak: 'break-word' as const,
            whiteSpace: 'pre-wrap' as const,
            color: '#d1e8d1',
            display: 'flex',
          }}>
            <span style={{
              color: '#4ade8030', userSelect: 'none', minWidth: 36, textAlign: 'right',
              paddingRight: 8, fontSize: 11, lineHeight: '1.75', flexShrink: 0,
            }}>{lineNum}</span>
            <span style={{ color: '#4ade8060', userSelect: 'none', flexShrink: 0 }}>{'> '}</span>
            <span style={{ flex: 1 }}>{line}</span>
          </div>
        );
      })}
      {isActive && (
        <div style={{ padding: '1px 0', display: 'flex' }}>
          <span style={{ minWidth: 36, paddingRight: 8, flexShrink: 0 }} />
          <span style={{ color: '#4ade80' }}>$</span>
          <span className="terminal-cursor" />
        </div>
      )}
    </>
  );
}

function FloatingWindow({
  agentName, eventId, messages, onClose,
}: {
  agentName: string;
  eventId: string | null;
  messages: string[];
  onClose: () => void;
}) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const [pos, setPos] = useState({ x: 120, y: 80 });
  const [size, setSize] = useState({ width: 700, height: 500 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length]);

  return (
    <div style={{
      position: 'fixed', top: pos.y, left: pos.x,
      width: size.width, height: size.height,
      background: '#0f172a', border: `2px solid ${color}`,
      borderRadius: 12, zIndex: 1000, display: 'flex', flexDirection: 'column',
      boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
    }}>
      {/* Draggable header */}
      <div style={{
        padding: '8px 12px', background: '#1e293b', borderBottom: `1px solid ${color}33`,
        borderRadius: '10px 10px 0 0', cursor: 'move', display: 'flex',
        justifyContent: 'space-between', alignItems: 'center',
      }} onMouseDown={(e) => {
        dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
        const onMove = (ev: MouseEvent) => {
          if (!dragRef.current) return;
          setPos({ x: dragRef.current.origX + ev.clientX - dragRef.current.startX, y: dragRef.current.origY + ev.clientY - dragRef.current.startY });
        };
        const onUp = () => { dragRef.current = null; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ background: color, color: '#fff', padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>
            {agentName}
          </span>
          {eventId && <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>[{eventId}]</span>}
        </div>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 18, cursor: 'pointer', lineHeight: 1, padding: '0 4px' }}>×</button>
      </div>

      {/* Scrollable content */}
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: 12, fontFamily: 'monospace', fontSize: 13, lineHeight: '1.5', color: '#94a3b8' }}>
        <MessageCards messages={messages} color={color} />
      </div>

      {/* Resize handle */}
      <div style={{
        position: 'absolute', bottom: 0, right: 0, width: 16, height: 16,
        cursor: 'nwse-resize', borderRight: `2px solid ${color}66`, borderBottom: `2px solid ${color}66`, borderRadius: '0 0 10px 0',
      }} onMouseDown={(e) => {
        e.stopPropagation();
        resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: size.width, origH: size.height };
        const onMove = (ev: MouseEvent) => {
          if (!resizeRef.current) return;
          setSize({ width: Math.max(400, resizeRef.current.origW + ev.clientX - resizeRef.current.startX), height: Math.max(250, resizeRef.current.origH + ev.clientY - resizeRef.current.startY) });
        };
        const onUp = () => { resizeRef.current = null; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);
      }} />
    </div>
  );
}

export default function AgentStreamCard({ agentName, eventId, messages, isActive, ephemeral }: AgentStreamCardProps) {
  const color = ephemeral ? '#4ade80' : (ACTOR_COLORS[agentName] || '#6b7280');
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

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setUserScrolled(false);
    }
  }, []);

  if (ephemeral) {
    const borderColor = isActive ? '#4ade80' : '#334155';
    const glowShadow = isActive
      ? '0 0 8px rgba(74, 222, 128, 0.15), inset 0 1px 3px rgba(0,0,0,0.5)'
      : 'inset 0 1px 3px rgba(0,0,0,0.5)';

    return (
      <>
        <div style={{
          flex: 1, minWidth: 0, background: '#030712',
          borderRadius: 6, border: `1px solid ${borderColor}`,
          display: 'flex', flexDirection: 'column',
          boxShadow: glowShadow,
          overflow: 'hidden', minHeight: 0,
          transition: 'border-color 0.3s, box-shadow 0.3s',
        }}>
          {/* Title bar */}
          <div style={{
            padding: '4px 10px', background: '#0d1117', borderBottom: `1px solid ${isActive ? '#4ade8033' : '#1e293b'}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ display: 'flex', gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }} />
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} />
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e' }} />
              </div>
              <span style={{
                fontSize: 11, color: '#64748b', fontFamily: "'JetBrains Mono', monospace",
                letterSpacing: '0.02em',
              }}>
                {agentName}@{eventId?.slice(4, 16) || 'idle'}
              </span>
              {isActive && (
                <span style={{
                  fontSize: 10, color: '#4ade80', background: '#4ade8018', padding: '1px 6px',
                  borderRadius: 4, fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
                }}>LIVE</span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <button
                onClick={() => { navigator.clipboard.writeText(messages.join('\n')); }}
                title="Copy stream" aria-label="Copy stream"
                className="hover:bg-white/10 hover:border-white/20 transition-colors"
                style={{
                  background: '#4ade8008', border: '1px solid #4ade8025', color: '#64748b',
                  cursor: 'pointer', padding: 0, borderRadius: 5,
                  width: 24, height: 24, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}
              ><Copy size={11} /></button>
              <button
                onClick={() => setPoppedOut(true)}
                title="Pop out" aria-label="Pop out"
                className="hover:bg-white/10 hover:border-white/20 transition-colors"
                style={{
                  background: '#4ade8008', border: '1px solid #4ade8025', color: '#64748b',
                  cursor: 'pointer', padding: 0, borderRadius: 5,
                  width: 24, height: 24, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}
              ><ExternalLink size={11} /></button>
            </div>
          </div>

          {/* Terminal body */}
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="terminal-scroll"
            style={{
              flex: 1, overflow: 'auto', padding: '6px 8px',
              background: '#030712', minHeight: 0,
            }}
          >
            <TerminalView messages={messages} isActive={isActive} />
          </div>

          {/* Status bar */}
          <div style={{
            padding: '2px 10px', background: '#0d1117', borderTop: `1px solid ${isActive ? '#4ade8033' : '#1e293b'}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0,
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace", color: '#4b5563',
          }}>
            <span>Ln {messages.length}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {userScrolled && (
                <button
                  onClick={scrollToBottom}
                  style={{
                    background: '#4ade8018', border: '1px solid #4ade8033', color: '#4ade80',
                    fontSize: 10, cursor: 'pointer', padding: '0 6px', borderRadius: 3,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >&#x25BC; Follow</button>
              )}
              <span>{isActive ? 'streaming' : messages.length > 0 ? 'done' : 'idle'}</span>
            </div>
          </div>
        </div>

        {poppedOut && (
          <FloatingWindow agentName={agentName} eventId={eventId} messages={messages} onClose={() => setPoppedOut(false)} />
        )}
      </>
    );
  }

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
              onClick={() => { navigator.clipboard.writeText(messages.join('\n')); }}
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
