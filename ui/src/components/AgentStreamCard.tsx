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
