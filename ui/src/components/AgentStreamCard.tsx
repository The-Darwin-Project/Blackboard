// BlackBoard/ui/src/components/AgentStreamCard.tsx
// @ai-rules:
// 1. [Pattern]: When agentName === 'developer' and huddleMessages has items, render chat layout.
// 2. [Pattern]: Three bubble styles: dev (left green), qe (right purple), flash (center gray).
// 3. [Pattern]: Architect and SysAdmin cards use legacy single-stream layout (messages[]).
// 4. [Pattern]: FloatingWindow also supports chat mode via huddleMessages prop.
/**
 * Real-time streaming card for agent CLI output.
 * Developer card transforms into a pair programming chat when QE is active.
 */
import { useEffect, useRef, useState } from 'react';
import { ACTOR_COLORS } from '../constants/colors';
import type { HuddleMessage } from './Dashboard';

interface AgentStreamCardProps {
  agentName: string;
  eventId: string | null;
  messages: string[];
  huddleMessages?: HuddleMessage[];
  isActive: boolean;
}

/** Render a single chat bubble (used by both inline card and FloatingWindow). */
function ChatBubble({ msg }: { msg: HuddleMessage }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: msg.actor === 'developer' ? 'flex-start'
                    : msg.actor === 'qe' ? 'flex-end'
                    : 'center',
      marginBottom: 4,
    }}>
      <div style={{
        maxWidth: '80%',
        padding: '4px 10px',
        borderRadius: 8,
        fontSize: msg.actor === 'flash' ? 11 : 12,
        fontFamily: 'monospace',
        lineHeight: '1.4',
        wordBreak: 'break-word' as const,
        whiteSpace: 'pre-wrap' as const,
        background: msg.actor === 'developer' ? 'rgba(16, 185, 129, 0.12)'
                  : msg.actor === 'qe' ? 'rgba(168, 85, 247, 0.12)'
                  : 'rgba(100, 116, 139, 0.08)',
        borderLeft: msg.actor === 'developer' ? '3px solid #22c55e' : 'none',
        borderRight: msg.actor === 'qe' ? '3px solid #8b5cf6' : 'none',
        color: msg.actor === 'flash' ? '#64748b' : '#94a3b8',
        fontStyle: msg.actor === 'flash' ? 'italic' : 'normal',
      }}>
        {msg.text}
      </div>
    </div>
  );
}

/** Render legacy single-stream lines (architect, sysadmin). */
function StreamLines({ messages, color }: { messages: string[]; color: string }) {
  return (
    <>
      {messages.length === 0 ? (
        <div style={{ color: '#334155', fontStyle: 'italic', fontSize: 11 }}>Idle</div>
      ) : (
        messages.slice(-50).map((line, i) => (
          <div key={i} style={{ marginBottom: 2, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
            <span style={{ color: `${color}77` }}>{'>'} </span>
            {line}
          </div>
        ))
      )}
    </>
  );
}

function FloatingWindow({
  agentName, eventId, messages, huddleMessages, onClose,
}: {
  agentName: string;
  eventId: string | null;
  messages: string[];
  huddleMessages: HuddleMessage[];
  onClose: () => void;
}) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const [pos, setPos] = useState({ x: 120, y: 80 });
  const [size, setSize] = useState({ width: 700, height: 500 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isChatMode = agentName === 'developer' && huddleMessages.length > 0;

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length, huddleMessages.length]);

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
          {agentName === 'developer' && (
            <span style={{ background: ACTOR_COLORS['qe'] || '#a855f7', color: '#fff', padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>
              qe
            </span>
          )}
          {eventId && <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>[{eventId}]</span>}
        </div>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 18, cursor: 'pointer', lineHeight: 1, padding: '0 4px' }}>×</button>
      </div>

      {/* Scrollable content */}
      <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: 12, fontFamily: 'monospace', fontSize: 13, lineHeight: '1.5', color: '#94a3b8' }}>
        {isChatMode ? (
          huddleMessages.map((msg, i) => <ChatBubble key={i} msg={msg} />)
        ) : (
          <StreamLines messages={messages} color={color} />
        )}
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

export default function AgentStreamCard({ agentName, eventId, messages, huddleMessages = [], isActive }: AgentStreamCardProps) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const scrollRef = useRef<HTMLDivElement>(null);
  const [poppedOut, setPoppedOut] = useState(false);
  const isChatMode = agentName === 'developer' && huddleMessages.length > 0;

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length, huddleMessages.length]);

  return (
    <>
      <div style={{
        flex: 1, minWidth: 0, background: '#0f172a',
        borderRadius: 8, border: `1px solid ${isActive ? color : '#334155'}`,
        display: 'flex', flexDirection: 'column',
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
            {agentName === 'developer' && (
              <span style={{ background: ACTOR_COLORS['qe'] || '#a855f7', color: '#fff', padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
                qe
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => {
                const text = isChatMode
                  ? huddleMessages.map(m => `[${m.actor}] ${m.text}`).join('\n')
                  : messages.join('\n');
                navigator.clipboard.writeText(text);
              }}
              title="Copy stream"
              style={{
                background: 'transparent', border: 'none', color: '#64748b',
                fontSize: 13, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
              }}
            >
              &#x2398;
            </button>
            <button onClick={() => setPoppedOut(true)} title="Pop out" style={{
              background: 'transparent', border: 'none', color: '#64748b', fontSize: 14, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
            }}>⧉</button>
          </div>
        </div>

        {/* Scrollable body */}
        <div ref={scrollRef} style={{
          flex: 1, overflow: 'auto', padding: '6px 10px', fontFamily: 'monospace',
          fontSize: 12, lineHeight: '1.4', color: '#94a3b8',
        }}>
          {isChatMode ? (
            huddleMessages.slice(-50).map((msg, i) => <ChatBubble key={i} msg={msg} />)
          ) : (
            <StreamLines messages={messages} color={color} />
          )}
        </div>
      </div>

      {/* Floating window */}
      {poppedOut && (
        <FloatingWindow
          agentName={agentName} eventId={eventId}
          messages={messages} huddleMessages={huddleMessages}
          onClose={() => setPoppedOut(false)}
        />
      )}
    </>
  );
}
