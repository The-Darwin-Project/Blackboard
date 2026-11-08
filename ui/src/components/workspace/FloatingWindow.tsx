// BlackBoard/ui/src/components/workspace/FloatingWindow.tsx
// @ai-rules:
// 1. [Pattern]: Reusable, viewport-clamped floating window with drag, resize, and unmount listener cleanup.
// 2. [Constraint]: Clamps pos.x and pos.y so window header cannot be dragged off-screen.
// 3. [Constraint]: Enforces minWidth (320px) and minHeight (220px) on resize and initial render.
// 4. [Constraint]: Re-clamps window on viewport resize events.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, X } from 'lucide-react';
import { ACTOR_COLORS } from '../../constants/colors';
import { sanitizeClipboardText } from './CopyButton';

export interface FloatingWindowProps {
  agentName: string;
  eventId: string | null;
  messages?: string[];
  onClose: () => void;
}

const MIN_WIDTH = 320;
const MIN_HEIGHT = 220;

export function FloatingWindow({
  agentName,
  eventId,
  messages = [],
  onClose,
}: FloatingWindowProps) {
  const color = ACTOR_COLORS[agentName] || '#6b7280';
  const [pos, setPos] = useState({ x: 120, y: 80 });
  const [size, setSize] = useState({ width: 700, height: 500 });

  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Active listener cleanup refs for unmount safety
  const cleanupDragRef = useRef<(() => void) | null>(null);
  const cleanupResizeRef = useRef<(() => void) | null>(null);

  // Synchronous refs to prevent listener churn in resize effect
  const posRef = useRef(pos);
  posRef.current = pos;
  const sizeRef = useRef(size);
  sizeRef.current = size;

  // Auto-scroll when messages update
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages?.length]);

  // Ensure window listeners are cleaned up if component unmounts mid-drag or mid-resize
  useEffect(() => {
    return () => {
      if (cleanupDragRef.current) {
        cleanupDragRef.current();
        cleanupDragRef.current = null;
      }
      if (cleanupResizeRef.current) {
        cleanupResizeRef.current();
        cleanupResizeRef.current = null;
      }
    };
  }, []);

  // Window drag handler
  const handleMouseDownHeader = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    if (cleanupDragRef.current) {
      cleanupDragRef.current();
      cleanupDragRef.current = null;
    }
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origX: pos.x,
      origY: pos.y,
    };

    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const rawX = dragRef.current.origX + (ev.clientX - dragRef.current.startX);
      const rawY = dragRef.current.origY + (ev.clientY - dragRef.current.startY);

      // Clamp so window never goes off-screen (clamp against actual window size)
      const maxX = Math.max(0, window.innerWidth - size.width);
      const maxY = Math.max(0, window.innerHeight - size.height);
      const nextX = Math.min(Math.max(0, rawX), maxX);
      const nextY = Math.min(Math.max(0, rawY), maxY);

      setPos({ x: nextX, y: nextY });
    };

    const handleMouseUp = () => {
      dragRef.current = null;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      cleanupDragRef.current = null;
    };

    cleanupDragRef.current = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [pos.x, pos.y, size.width, size.height]);

  // Window resize handler
  const handleMouseDownResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (cleanupResizeRef.current) {
      cleanupResizeRef.current();
      cleanupResizeRef.current = null;
    }
    resizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origW: size.width,
      origH: size.height,
    };

    const handleMouseMove = (ev: MouseEvent) => {
      if (!resizeRef.current) return;
      const rawW = resizeRef.current.origW + (ev.clientX - resizeRef.current.startX);
      const rawH = resizeRef.current.origH + (ev.clientY - resizeRef.current.startY);

      const maxW = Math.max(MIN_WIDTH, window.innerWidth - pos.x);
      const maxH = Math.max(MIN_HEIGHT, window.innerHeight - pos.y);

      const nextW = Math.min(Math.max(MIN_WIDTH, rawW), maxW);
      const nextH = Math.min(Math.max(MIN_HEIGHT, rawH), maxH);

      setSize({ width: nextW, height: nextH });
    };

    const handleMouseUp = () => {
      resizeRef.current = null;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      cleanupResizeRef.current = null;
    };

    cleanupResizeRef.current = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [size.width, size.height, pos.x, pos.y]);

  // Viewport resize re-clamping (uses refs to avoid listener churn on drag)
  useEffect(() => {
    const handleViewportResize = () => {
      const curSize = sizeRef.current;
      const curPos = posRef.current;
      const nextW = Math.min(curSize.width, Math.max(MIN_WIDTH, window.innerWidth));
      const nextH = Math.min(curSize.height, Math.max(MIN_HEIGHT, window.innerHeight));
      const maxX = Math.max(0, window.innerWidth - nextW);
      const maxY = Math.max(0, window.innerHeight - nextH);
      const nextX = Math.min(Math.max(0, curPos.x), maxX);
      const nextY = Math.min(Math.max(0, curPos.y), maxY);

      setPos({ x: nextX, y: nextY });
      setSize({ width: nextW, height: nextH });
    };

    window.addEventListener('resize', handleViewportResize);
    return () => {
      window.removeEventListener('resize', handleViewportResize);
    };
  }, []);

  const handleCopyLogs = useCallback(() => {
    if (messages && messages.length > 0) {
      const sanitized = sanitizeClipboardText(messages.join('\n'));
      navigator.clipboard?.writeText(sanitized).catch(() => {});
    }
  }, [messages]);

  return (
    <div
      data-testid="floating-window"
      style={{
        position: 'fixed',
        top: pos.y,
        left: pos.x,
        width: size.width,
        height: size.height,
        background: '#0f172a',
        border: `2px solid ${color}`,
        borderRadius: 12,
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }}
    >
      {/* Draggable header */}
      <div
        onMouseDown={handleMouseDownHeader}
        style={{
          padding: '8px 12px',
          background: '#1e293b',
          borderBottom: `1px solid ${color}33`,
          borderRadius: '10px 10px 0 0',
          cursor: 'move',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          userSelect: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: color,
              boxShadow: `0 0 8px ${color}`,
            }}
          />
          <span style={{ color, fontWeight: 700, fontSize: 13, textTransform: 'capitalize' }}>
            {agentName}
          </span>
          {eventId && (
            <span style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace' }}>
              {eventId}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={handleCopyLogs}
            aria-label="Copy logs"
            title="Copy logs"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              padding: 2,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Copy size={13} />
          </button>
          <button
            onClick={onClose}
            aria-label="Close"
            title="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: 16,
              lineHeight: 1,
              padding: '0 4px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Messages body */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 12px',
          background: '#090d16',
        }}
      >
        {(!messages || messages.length === 0) ? (
          <div style={{ color: '#334155', fontStyle: 'italic', fontSize: 11 }}>Idle</div>
        ) : (
          messages.slice(-100).map((line, i) => (
            <div
              key={i}
              style={{
                marginBottom: 4,
                padding: '4px 10px',
                borderRadius: 8,
                borderLeft: `3px solid ${color}`,
                background: `${color}12`,
                fontSize: 12,
                fontFamily: 'monospace',
                lineHeight: '1.4',
                wordBreak: 'break-word',
                whiteSpace: 'pre-wrap',
                color: '#94a3b8',
              }}
            >
              {line}
            </div>
          ))
        )}
      </div>

      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDownResize}
        style={{
          position: 'absolute',
          bottom: 0,
          right: 0,
          width: 16,
          height: 16,
          cursor: 'nwse-resize',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'flex-end',
          padding: 2,
        }}
      >
        <div
          style={{
            width: 0,
            height: 0,
            borderStyle: 'solid',
            borderWidth: '0 0 8px 8px',
            borderColor: `transparent transparent ${color}66 transparent`,
          }}
        />
      </div>
    </div>
  );
}

export default FloatingWindow;
