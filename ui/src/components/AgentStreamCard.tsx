// BlackBoard/ui/src/components/AgentStreamCard.tsx
/**
 * Real-time streaming card for a single agent's Gemini CLI output.
 * Shows action narration lines streamed via WebSocket progress messages.
 * Supports pop-out into a draggable/resizable floating window.
 */
import { useEffect, useRef, useState } from 'react';
import { ACTOR_COLORS } from '../constants/colors';

interface AgentStreamCardProps {
  agentName: string;
  eventId: string | null;
  messages: string[];
  isActive: boolean;
}

function FloatingWindow({
  agentName,
  eventId,
  messages,
  onClose,
}: {
  agentName: string;
  eventId: string | null;
  messages: string[];
  onClose: () => void;
}) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const [pos, setPos] = useState({ x: 120, y: 80 });
  const [size] = useState({ width: 700, height: 500 });
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  return (
    <div
      style={{
        position: 'fixed', top: pos.y, left: pos.x,
        width: size.width, height: size.height,
        background: '#0f172a', border: `2px solid ${color}`,
        borderRadius: 12, zIndex: 1000, display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }}
    >
      {/* Draggable header */}
      <div
        style={{
          padding: '8px 12px', background: '#1e293b', borderBottom: `1px solid ${color}33`,
          borderRadius: '10px 10px 0 0', cursor: 'move', display: 'flex',
          justifyContent: 'space-between', alignItems: 'center',
        }}
        onMouseDown={(e) => {
          dragRef.current = { startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
          const onMove = (ev: MouseEvent) => {
            if (!dragRef.current) return;
            setPos({
              x: dragRef.current.origX + ev.clientX - dragRef.current.startX,
              y: dragRef.current.origY + ev.clientY - dragRef.current.startY,
            });
          };
          const onUp = () => {
            dragRef.current = null;
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
          };
          window.addEventListener('mousemove', onMove);
          window.addEventListener('mouseup', onUp);
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            background: color, color: '#fff', padding: '2px 10px',
            borderRadius: 12, fontSize: 12, fontWeight: 600,
          }}>
            {agentName}
          </span>
          {eventId && (
            <span style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
              [{eventId}]
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'transparent', border: 'none', color: '#94a3b8',
            fontSize: 18, cursor: 'pointer', lineHeight: 1, padding: '0 4px',
          }}
        >
          ×
        </button>
      </div>

      {/* Scrollable content */}
      <div
        ref={scrollRef}
        style={{
          flex: 1, overflow: 'auto', padding: 12, fontFamily: 'monospace',
          fontSize: 13, lineHeight: '1.5', color: '#94a3b8',
        }}
      >
        {messages.length === 0 ? (
          <div style={{ color: '#475569', fontStyle: 'italic' }}>Idle -- waiting for tasks</div>
        ) : (
          messages.map((line, i) => (
            <div key={i} style={{ marginBottom: 4, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
              <span style={{ color: `${color}99` }}>{'>'} </span>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function AgentStreamCard({ agentName, eventId, messages, isActive }: AgentStreamCardProps) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const scrollRef = useRef<HTMLDivElement>(null);
  const [poppedOut, setPoppedOut] = useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  return (
    <>
      <div
        style={{
          flex: 1, minWidth: 0, background: '#0f172a',
          borderRadius: 8, border: `1px solid ${isActive ? color : '#334155'}`,
          display: 'flex', flexDirection: 'column',
          opacity: isActive ? 1 : 0.6, transition: 'opacity 0.3s, border-color 0.3s',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '6px 10px', borderBottom: `1px solid ${isActive ? color + '33' : '#1e293b'}`,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{
              background: color, color: '#fff', padding: '1px 8px',
              borderRadius: 10, fontSize: 11, fontWeight: 600,
            }}>
              {agentName}
            </span>
            {eventId && (
              <span style={{ fontSize: 10, color: '#64748b', fontFamily: 'monospace' }}>
                [{eventId.slice(0, 12)}]
              </span>
            )}
            {isActive && (
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#22c55e', display: 'inline-block',
              }} />
            )}
          </div>
          <button
            onClick={() => setPoppedOut(true)}
            title="Pop out"
            style={{
              background: 'transparent', border: 'none', color: '#64748b',
              fontSize: 14, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
            }}
          >
            ⧉
          </button>
        </div>

        {/* Scrollable body */}
        <div
          ref={scrollRef}
          style={{
            flex: 1, overflow: 'auto', padding: '6px 10px', fontFamily: 'monospace',
            fontSize: 12, lineHeight: '1.4', color: '#94a3b8', maxHeight: 200,
          }}
        >
          {messages.length === 0 ? (
            <div style={{ color: '#334155', fontStyle: 'italic', fontSize: 11 }}>
              Idle
            </div>
          ) : (
            messages.slice(-50).map((line, i) => (
              <div key={i} style={{ marginBottom: 2, wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                <span style={{ color: `${color}77` }}>{'>'} </span>
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Floating window */}
      {poppedOut && (
        <FloatingWindow
          agentName={agentName}
          eventId={eventId}
          messages={messages}
          onClose={() => setPoppedOut(false)}
        />
      )}
    </>
  );
}
